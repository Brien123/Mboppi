from django.db.models.signals import post_save
from django.dispatch import receiver
from dateutil.relativedelta import relativedelta
from .models import Order, PaymentInstallment

@receiver(post_save, sender=Order)
def create_installments(sender, instance, created, **kwargs):
    if created:
        total_base = instance.total_base_price
        total_local = instance.total_local_price
        plan = instance.payment_plan

        plan_config = {
            'FP': (1, 'months'),
            '4W': (4, 'weeks'),
            '2M': (2, 'months'),
            '4M': (4, 'months'),
            '6M': (6, 'months'),
            '12M': (12, 'months'),
        }

        count, unit = plan_config[plan]

        base_per = total_base / count
        local_per = total_local / count

        due_date = instance.created_at.date()
        installments = []
        for i in range(count):
            installments.append(PaymentInstallment(
                order=instance,
                due_date=due_date,
                amount_base=base_per,
                amount_local=local_per
            ))
            
            if unit == 'weeks':
                due_date += relativedelta(weeks=1)
            else:
                due_date += relativedelta(months=1)

        PaymentInstallment.objects.bulk_create(installments)