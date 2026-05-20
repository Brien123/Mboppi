import uuid
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from orders.models import PaymentInstallment, Order
from payments.models import Transaction, FlutterwaveCustomer
from payments.utils import FlutterwaveService
import logging

logging.basicConfig(level=logging.INFO)

def send_payment_failure_notification(installment, reason):
    """
    Sends an email notification to the user about a failed payment installment.
    """
    try:
        user = installment.order.user
        if not user or not user.email:
            return False
            
        context = {
            'user_name': user.first_name or user.username,
            'order_id': installment.order.order_id.hex[:10].upper(),
            'due_date': installment.due_date.strftime('%Y-%m-%d'),
            'amount': installment.amount_local,
            'currency': installment.order.currency_code,
            'reason': reason
        }
        
        subject = f"Payment Failed for Order #{context['order_id']}"
        html_content = render_to_string('payments/email/payment_failed.html', context)
        text_content = render_to_string('payments/email/payment_failed.txt', context)
        
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        return True
    except Exception as e:
        # Log error but don't crash the task
        logging.error(f"Failed to send failure notification for installment {installment.id}: {str(e)}")
        return False

@shared_task
def process_scheduled_payments():
    """
    Task to process all due payment installments.
    """
    today = timezone.now().date()
    # Get all unpaid installments that are due or overdue
    due_installments = PaymentInstallment.objects.filter(
        is_paid=False,
        due_date__lte=today,
        order__status__in=['active', 'pending']
    )

    results = {
        "total": due_installments.count(),
        "succeeded": 0,
        "failed": 0,
        "errors": []
    }

    service = FlutterwaveService()

    for installment in due_installments:
        try:
            order = installment.order
            user = order.user
            
            if not hasattr(user, 'flutterwave_customer'):
                reason = f"User {user.id} has no Flutterwave customer object."
                results["errors"].append(f"Installment {installment.id}: {reason}")
                results["failed"] += 1
                send_payment_failure_notification(installment, "No registered payment profile found.")
                continue

            customer = user.flutterwave_customer
            payment_method = customer.payment_methods.filter(is_active=True, is_default=True).first() or customer.payment_methods.filter(is_active=True).first()


            if not payment_method:
                reason = f"No active payment method for customer {customer.flutterwave_customer_id}."
                results["errors"].append(f"Installment {installment.id}: {reason}")
                results["failed"] += 1
                send_payment_failure_notification(installment, "No active payment method on file.")
                continue

            reference = f"auto_charge_{order.order_id.hex[:10]}_{installment.id}"
            idempotency_key = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())

            # Initiate charge
            fl_response = service.charge_card_object(
                reference=reference,
                currency=order.currency_code,
                customer_id=customer.flutterwave_customer_id,
                payment_method_id=payment_method.flutterwave_payment_method_id,
                amount=float(installment.amount_local),
                redirect_url=settings.FLUTTERWAVE_REDIRECT_URL,
                idempotency_key=idempotency_key,
                trace_id=trace_id
            )

            status_str = fl_response.get('status')
            data = fl_response.get('data', {})

            if status_str == 'success':
                charge_status = data.get('status')
                is_paid = charge_status and charge_status.lower() in ('successful', 'succeeded')

                transaction = Transaction.objects.create(
                    customer=customer,
                    payment_method=payment_method,
                    flutterwave_charge_id=str(data.get('id', '')),
                    reference=reference,
                    amount=installment.amount_local,
                    currency=order.currency_code,
                    status='succeeded' if is_paid else 'failed',
                    idempotency_key=idempotency_key,
                    trace_id=trace_id,
                    order=order
                )

                installment.transaction = transaction
                if is_paid:
                    installment.is_paid = True
                    installment.paid_at = timezone.now()
                    results["succeeded"] += 1
                    
                    # Check if all installments are paid
                    if not order.installments.filter(is_paid=False).exists():
                        order.status = 'completed'
                        order.save()
                else:
                    results["failed"] += 1
                    # Notify user about failed charge status
                    charge_msg = data.get('processor_response', 'The charge was declined.')
                    send_payment_failure_notification(installment, charge_msg)
                
                installment.save()
            else:
                results["failed"] += 1
                fail_reason = fl_response.get('message', 'The payment request failed.')
                results["errors"].append(f"Installment {installment.id}: Charge failed. {fail_reason}")
                send_payment_failure_notification(installment, fail_reason)

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Installment {installment.id}: Exception: {str(e)}")
            send_payment_failure_notification(installment, "An unexpected error occurred while processing your payment.")

    return results

@shared_task
def send_payment_reminders():
    """
    Task to send reminders for installments due tomorrow.
    """
    tomorrow = (timezone.now() + timedelta(days=1)).date()
    due_tomorrow = PaymentInstallment.objects.filter(
        is_paid=False,
        due_date=tomorrow,
        order__status__in=['active', 'pending']
    ).select_related('order', 'order__user')

    results = {
        "sent": 0,
        "failed": 0,
        "errors": []
    }

    for installment in due_tomorrow:
        try:
            user = installment.order.user
            if not user.email:
                continue
                
            context = {
                'user_name': user.first_name or user.username,
                'order_id': installment.order.order_id.hex[:10].upper(),
                'due_date': installment.due_date.strftime('%Y-%m-%d'),
                'amount': installment.amount_local,
                'currency': installment.order.currency_code
            }
            
            subject = f"Reminder: Payment due tomorrow for Order #{context['order_id']}"
            html_content = render_to_string('payments/email/payment_reminder.html', context)
            text_content = render_to_string('payments/email/payment_reminder.txt', context)
            
            email = EmailMultiAlternatives(
                subject,
                text_content,
                settings.DEFAULT_FROM_EMAIL,
                [user.email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            
            results["sent"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Installment {installment.id}: {str(e)}")
            
    return results
