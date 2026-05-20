import json
import hmac
import hashlib
from typing import Dict, Any, Optional
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from .models import WebhookEvent, Transaction


class FlutterwaveWebhookService:
    """
    Service for handling Flutterwave webhooks.
    Verifies webhook signatures, deduplicates events, and processes them.
    """

    @staticmethod
    def verify_webhook_signature(headers: Dict[str, str], body: bytes) -> bool:
        """
        Verify Flutterwave webhook signature using HMAC-SHA256.
        
        Flutterwave sends:
        - X-Flutterwave-Signature: HMAC-SHA256 of the body using the webhook secret
        
        Handles both standard HTTP headers and Django WSGI format (HTTP_* prefixed).
        
        :param headers: Request headers (case-insensitive, can be dict or WSGI format)
        :param body: Raw request body
        :return: True if signature is valid, False otherwise
        """
        webhook_secret = settings.FLUTTERWAVE_WEBHOOK_SECRET
        if not webhook_secret:
            # If no secret configured, skip verification (not recommended for production)
            return True
        
        # Get the signature from headers (handle both standard and WSGI formats)
        signature_header = None
        for key, value in headers.items():
            # Check standard format: X-Flutterwave-Signature
            # Also check WSGI format: HTTP_X_FLUTTERWAVE_SIGNATURE
            normalized_key = key.lower().replace('http_', '').replace('_', '-')
            if normalized_key == 'x-flutterwave-signature':
                signature_header = value
                break
        
        if not signature_header:
            return False
        
        # Compute HMAC-SHA256
        computed_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures using constant-time comparison
        return hmac.compare_digest(computed_signature, signature_header)

    @staticmethod
    def process_webhook(payload: Dict[str, Any]) -> bool:
        """
        Process a Flutterwave webhook payload.
        
        Steps:
        1. Validate payload structure
        2. Check for idempotency (event_id uniqueness)
        3. Create WebhookEvent record
        4. Route to appropriate handler based on event_type
        5. Update processing status
        
        :param payload: Parsed webhook payload from Flutterwave
        :return: True if processed successfully, False otherwise
        """
        try:
            # Extract key fields
            event_id = payload.get('webhook_id')
            event_type = payload.get('type')
            
            if not event_id or not event_type:
                raise ValueError("Missing webhook_id or type in payload")
            
            # Check for duplicate using event_id
            with db_transaction.atomic():
                webhook_event, created = WebhookEvent.objects.get_or_create(
                    event_id=event_id,
                    defaults={
                        'provider': 'flutterwave',
                        'event_type': event_type,
                        'payload': payload,
                        'status': 'pending'
                    }
                )
                
                # If event already exists, return success (already processed or in progress)
                if not created:
                    if webhook_event.status in ['processed', 'processing']:
                        return True
                    # If failed, attempt reprocessing
                    webhook_event.status = 'processing'
                    webhook_event.retry_count += 1
                    webhook_event.save(update_fields=['status', 'retry_count'])
                else:
                    webhook_event.status = 'processing'
                    webhook_event.save(update_fields=['status'])
                
                # Route to handler
                handler_method = getattr(
                    FlutterwaveWebhookService,
                    f'_handle_{event_type.replace(".", "_")}',
                    None
                )
                
                if not handler_method:
                    # Unknown event type - mark as ignored
                    webhook_event.status = 'ignored'
                    webhook_event.error_message = f'No handler for event type: {event_type}'
                    webhook_event.processed_at = timezone.now()
                    webhook_event.save()
                    return True
                
                # Execute handler
                try:
                    handler_method(payload)
                    webhook_event.status = 'processed'
                    webhook_event.processed_at = timezone.now()
                    webhook_event.save(update_fields=['status', 'processed_at'])
                    return True
                except Exception as e:
                    webhook_event.status = 'failed'
                    webhook_event.error_message = str(e)
                    webhook_event.processed_at = timezone.now()
                    webhook_event.save(update_fields=['status', 'error_message', 'processed_at'])
                    raise
        
        except Exception as e:
            import traceback; traceback.print_exc()
            return False

    @staticmethod
    def _handle_charge_completed(payload: Dict[str, Any]) -> None:
        """
        Handle charge.completed event.
        
        Updates the corresponding Transaction and related Order/PaymentInstallment status.
        """
        data = payload.get('data', {})
        charge_id = data.get('id')
        reference = data.get('reference')
        
        if not charge_id and not reference:
            raise ValueError("charge.completed event missing charge ID or reference")
        
        # Find transaction by charge ID or reference
        # (process_webhook already runs in an atomic block)
        transaction_obj = None
        
        if charge_id:
            transaction_obj = Transaction.objects.filter(
                flutterwave_charge_id=charge_id
            ).first()
        
        if not transaction_obj and reference:
            transaction_obj = Transaction.objects.filter(
                reference=reference
            ).first()
        
        if not transaction_obj:
            raise ValueError(f"Transaction not found for charge {charge_id} or reference {reference}")
        
        # Update transaction status
        charge_status = data.get('status', '').lower()
        is_succeeded = charge_status in ('successful', 'succeeded')
        
        transaction_obj.status = 'succeeded' if is_succeeded else 'pending'
        transaction_obj.save(update_fields=['status'])
        
        # Update related order and installments
        if is_succeeded and transaction_obj.order:
            order = transaction_obj.order
            
            # Update order status if first payment
            if order.status == 'pending':
                order.status = 'active'
                order.save(update_fields=['status'])
            
            # Find and update installments linked to this transaction
            from orders.models import PaymentInstallment
            PaymentInstallment.objects.filter(
                transaction=transaction_obj,
                is_paid=False
            ).update(
                is_paid=True,
                paid_at=timezone.now()
            )

    @staticmethod
    def _handle_charge_failed(payload: Dict[str, Any]) -> None:
        """
        Handle charge.failed event.
        
        Marks the transaction as failed but leaves order/payment installments in current state.
        """
        data = payload.get('data', {})
        charge_id = data.get('id')
        reference = data.get('reference')
        
        if not charge_id and not reference:
            raise ValueError("charge.failed event missing charge ID or reference")
        
        # (process_webhook already runs in an atomic block)
        transaction_obj = None
        
        if charge_id:
            transaction_obj = Transaction.objects.filter(
                flutterwave_charge_id=charge_id
            ).first()
        
        if not transaction_obj and reference:
            transaction_obj = Transaction.objects.filter(
                reference=reference
            ).first()
        
        if not transaction_obj:
            raise ValueError(f"Transaction not found for charge {charge_id} or reference {reference}")
        
        # Mark as failed
        transaction_obj.status = 'failed'
        transaction_obj.save(update_fields=['status'])

    @staticmethod
    def _handle_subscription_created(payload: Dict[str, Any]) -> None:
        """
        Handle subscription.created event (if needed).
        """
        pass

    @staticmethod
    def _handle_subscription_cancelled(payload: Dict[str, Any]) -> None:
        """
        Handle subscription.cancelled event (if needed).
        """
        from .models import Subscription
        
        data = payload.get('data', {})
        subscription_id = data.get('id')
        
        if not subscription_id:
            raise ValueError("subscription.cancelled event missing subscription ID")
        
        with db_transaction.atomic():
            sub = Subscription.objects.filter(
                flutterwave_subscription_id=subscription_id
            ).select_for_update().first()
            
            if sub:
                sub.status = 'cancelled'
                sub.cancelled_at = timezone.now()
                sub.save(update_fields=['status', 'cancelled_at'])
