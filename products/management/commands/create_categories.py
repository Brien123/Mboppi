from django.core.management.base import BaseCommand
from products.models import Category
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Create initial product categories'

    def handle(self, *args, **kwargs):
        categories = [
            'Electronics',
            'Appliances',
            'Fashion',
            'Health and Beauty',
            'Education Supplies',
            'Home Goods'
        ]

        for cat_name in categories:
            category, created = Category.objects.get_or_create(
                name=cat_name,
                defaults={'slug': slugify(cat_name)}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created category "{cat_name}"'))
            else:
                self.stdout.write(self.style.WARNING(f'Category "{cat_name}" already exists'))
