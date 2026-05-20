from django.core.management.base import BaseCommand
from products.tasks import train_recommendation_model
import json

class Command(BaseCommand):
    help = 'Trigger training for the collaborative filtering recommendation model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run the training task asynchronously using Celery',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Starting recommendation model training...'))
        
        if options['async']:
            self.stdout.write('Dispatching task to Celery...')
            task = train_recommendation_model.delay()
            self.stdout.write(self.style.SUCCESS(f'Task dispatched with ID: {task.id}'))
        else:
            self.stdout.write('Running training synchronously...')
            result = train_recommendation_model()
            
            if result.get('status') == 'success':
                self.stdout.write(self.style.SUCCESS('Training completed successfully!'))
                self.stdout.write(json.dumps(result.get('stats'), indent=2))
            elif result.get('status') == 'skipped':
                self.stdout.write(self.style.WARNING(f"Training skipped: {result.get('reason')}"))
                self.stdout.write(f"Interaction count: {result.get('count')}")
            else:
                self.stdout.write(self.style.ERROR(f"Training failed: {result.get('reason', 'Unknown error')}"))
                if 'error' in result:
                    self.stdout.write(self.style.ERROR(result['error']))
