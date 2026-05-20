import random
import string
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from common.models import Country
from products.models import Category, Product, ProductViewLog

User = get_user_model()

# ── Fake data pools ────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Amara", "Chidera", "Fatima", "Ngozi", "Zainab", "Emeka", "Tunde",
    "Aisha", "Kofi", "Kwame", "Adaeze", "Bola", "Chidi", "Damilola",
    "Eze", "Femi", "Grace", "Hassan", "Ifeoma", "Jide", "Kemi", "Lola",
    "Musa", "Nkem", "Ola", "Precious", "Qudus", "Rita", "Sade", "Tobi",
    "Uche", "Victor", "Wale", "Xolani", "Yetunde", "Zara", "Abel",
    "Blessing", "Collins", "Divine", "Ezinne", "Favour", "Gideon",
    "Helen", "Innocent", "Joy", "Kenechukwu", "Lekan", "Mary", "Nonso",
]

LAST_NAMES = [
    "Okafor", "Bello", "Adeyemi", "Nwosu", "Ibrahim", "Adesanya",
    "Chukwu", "Musa", "Obi", "Adeleke", "Eze", "Babatunde", "Nwachukwu",
    "Mohammed", "Olawale", "Onyeka", "Abubakar", "Okonkwo", "Taiwo",
    "Usman", "Adebayo", "Nwankwo", "Salisu", "Ogundele", "Ekwueme",
    "Lawal", "Nnaji", "Yakubu", "Olufemi", "Amaechi", "Dikko", "Garba",
    "Haruna", "Ikenna", "Jukwu", "Kolawole", "Ladan", "Mba", "Ndidi",
    "Okeke", "Peters", "Quadri", "Rasheed", "Suleiman", "Thomas",
    "Ugwu", "Vincent", "Waziri", "Yusuf", "Zubair",
]

PRODUCT_ADJECTIVES = [
    "Premium", "Classic", "Modern", "Luxury", "Essential", "Handcrafted",
    "Organic", "Signature", "Artisan", "Elite", "Fresh", "Royal",
    "Golden", "Silver", "Deluxe", "Pro", "Ultra", "Super", "Mega", "Mini",
]

PRODUCT_NOUNS = [
    "Bag", "Shoes", "Watch", "Perfume", "Dress", "Shirt", "Trouser",
    "Jacket", "Cap", "Belt", "Wallet", "Sunglasses", "Necklace",
    "Earrings", "Bracelet", "Ring", "Scarf", "Gloves", "Socks", "Tie",
    "Laptop Stand", "Phone Case", "Charger", "Headphones", "Speaker",
    "Backpack", "Tote Bag", "Sneakers", "Sandals", "Loafers",
]


IP_PREFIXES = [
    "102.89", "197.210", "41.58", "41.184", "197.255",
    "105.112", "196.216", "197.149", "154.120", "41.203",
]


def _random_ip():
    prefix = random.choice(IP_PREFIXES)
    return f"{prefix}.{random.randint(0, 254)}.{random.randint(1, 254)}"


def _random_past_datetime(days_back=180):
    # Weight 30% of logs to be in the last 2 days for trending API
    if random.random() < 0.3:
        delta = timedelta(
            days=random.randint(0, 2),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
    else:
        delta = timedelta(
            days=random.randint(0, days_back),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
    return timezone.now() - delta


def _unique_username(first, last):
    base = slugify(f"{first}{last}").replace("-", "")
    suffix = "".join(random.choices(string.digits, k=4))
    return f"{base}{suffix}"


# ── Command ────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Seed the database with 50 random users, 50 random products, "
        "and 1 000 random product view logs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--users", type=int, default=50,
            help="Number of users to create (default: 50)",
        )
        parser.add_argument(
            "--products", type=int, default=50,
            help="Number of products to create (default: 50)",
        )
        parser.add_argument(
            "--logs", type=int, default=1000,
            help="Number of view logs to create (default: 1000)",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete all previously seeded test data before generating new data",
        )

    def handle(self, *args, **options):
        n_users = options["users"]
        n_products = options["products"]
        n_logs = options["logs"]

        if options["clear"]:
            self._clear_data()

        self.stdout.write(self.style.MIGRATE_HEADING("\n🌱  Starting test data generation…\n"))

        countries = list(Country.objects.filter(is_active=True))
        if not countries:
            self.stdout.write(self.style.WARNING("⚠️   No active countries found. Fetching all countries..."))
            countries = list(Country.objects.all())
        
        if not countries:
             self.stdout.write(self.style.WARNING("⚠️   No countries found at all. Trending may be empty."))

        users = self._create_users(n_users, countries)
        products = self._create_products(n_products)
        self._create_view_logs(n_logs, products, users, countries)

        self.stdout.write(self.style.SUCCESS(
            f"\n✅  Done!  Created {n_users} users · {n_products} products · {n_logs} view logs.\n"
        ))

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _clear_data(self):
        self.stdout.write("🗑️   Clearing previously seeded data…")
        ProductViewLog.objects.filter(ip_address__isnull=False).delete()
        Product.objects.filter(name__contains=" ").delete()
        User.objects.filter(is_staff=False, is_superuser=False).delete()
        self.stdout.write(self.style.WARNING("   Old data cleared.\n"))

    def _create_users(self, count, countries):
        self.stdout.write(f"👤  Creating {count} users…")
        created = []
        used_usernames = set(User.objects.values_list("username", flat=True))

        for _ in range(count):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            username = _unique_username(first, last)

            # Guarantee uniqueness
            while username in used_usernames:
                username = _unique_username(first, last)
            used_usernames.add(username)

            email = f"{username}@example.com"
            user = User.objects.create_user(
                username=username,
                email=email,
                password="Test@1234",
                first_name=first,
                last_name=last,
            )

            # Create profile if the signal hasn't done it already
            try:
                from profiles.models import Profile
                profile, _ = Profile.objects.get_or_create(user=user)
                if countries:
                    profile.country = random.choice(countries)
                    profile.phone = f"+234{random.randint(7000000000, 9099999999)}"
                    profile.save(update_fields=["country", "phone"])
            except Exception:
                pass  # profiles app may not be installed in all envs

            created.append(user)

        self.stdout.write(self.style.SUCCESS(f"   ✓ {count} users created."))
        return created

    def _create_products(self, count):
        self.stdout.write(f"📦  Creating {count} products…")

        # Use categories already in the DB (seeded by create_categories command)
        categories = list(Category.objects.all())
        if not categories:
            self.stdout.write(self.style.ERROR(
                "   No categories found. Run `manage.py create_categories` first."
            ))
            return []

        created = []
        used_names: set[str] = set(Product.objects.values_list("name", flat=True))

        for _ in range(count):
            # Build a unique product name
            attempts = 0
            while True:
                adj = random.choice(PRODUCT_ADJECTIVES)
                noun = random.choice(PRODUCT_NOUNS)
                suffix = random.choice(string.ascii_uppercase)
                name = f"{adj} {noun} {suffix}"
                if name not in used_names:
                    used_names.add(name)
                    break
                attempts += 1
                if attempts > 200:
                    # Fallback: append a short uuid fragment
                    name = f"{adj} {noun} {uuid.uuid4().hex[:4].upper()}"
                    used_names.add(name)
                    break

            product = Product(
                category=random.choice(categories),
                name=name,
                description=(
                    f"This is the {name.lower()}. "
                    "High quality, durable, and designed for everyday use."
                ),
                base_price=round(random.uniform(5.00, 999.99), 2),
                stock=random.randint(0, 500),
                is_active=random.choices([True, False], weights=[85, 15])[0],
            )
            product.save()  # triggers slug auto-generation in model.save()
            created.append(product)

        self.stdout.write(self.style.SUCCESS(f"   ✓ {count} products created."))
        return created

    def _create_view_logs(self, count, products, users, countries):
        self.stdout.write(f"👁️   Creating {count} product view logs…")

        if not products:
            self.stdout.write(self.style.WARNING("   No products found — skipping view logs."))
            return

        logs = []
        for _ in range(count):
            # ~60 % authenticated views, ~40 % anonymous
            user = random.choice(users) if users and random.random() < 0.6 else None
            country = random.choice(countries) if countries else None

            log = ProductViewLog(
                product=random.choice(products),
                user=user,
                country=country,
                ip_address=_random_ip(),
                # Override auto_now_add by using a raw save after creation
            )
            logs.append(log)

        # Bulk-create for speed
        ProductViewLog.objects.bulk_create(logs, batch_size=200)

        # Back-date the viewed_at timestamps to make analytics more realistic
        # (auto_now_add prevents setting it on the model directly, so we patch via queryset)
        all_log_ids = list(
            ProductViewLog.objects.order_by("-id").values_list("id", flat=True)[:count]
        )
        for log_id in all_log_ids:
            ProductViewLog.objects.filter(id=log_id).update(
                viewed_at=_random_past_datetime(days_back=180)
            )

        self.stdout.write(self.style.SUCCESS(f"   ✓ {count} view logs created."))
