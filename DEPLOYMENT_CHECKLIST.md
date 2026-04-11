# ManaBills PostgreSQL Deployment Checklist

Follow this checklist to deploy the PostgreSQL optimizations to your project.

---

## Pre-Deployment ✓

- [ ] Backup existing database (if using SQLite)
- [ ] Read [POSTGRESQL_SETUP.md](POSTGRESQL_SETUP.md)
- [ ] PostgreSQL 14+ installed locally or accessible
- [ ] Python 3.8+ with Django 6.0+

---

## Step 1: Install PostgreSQL Adapter

```bash
pip install psycopg2-binary
```

**Verify:**
```bash
python -c "import psycopg2; print(psycopg2.__version__)"
```

---

## Step 2: Create PostgreSQL Database

**On Windows (PowerShell):**
```bash
# Connect to PostgreSQL
psql -U postgres

# Then paste the following:
CREATE DATABASE manabills_db;
CREATE USER manabills_user WITH PASSWORD 'your_secure_password_123';
ALTER ROLE manabills_user SET client_encoding TO 'utf8';
ALTER ROLE manabills_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE manabills_user SET default_transaction_deferrable TO on;
ALTER ROLE manabills_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE manabills_db TO manabills_user;
\q

# Verify connection
psql -U manabills_user -d manabills_db -c "SELECT version();"
```

**On Linux/Mac:**
```bash
sudo -u postgres psql << EOF
CREATE DATABASE manabills_db;
CREATE USER manabills_user WITH PASSWORD 'your_secure_password_123';
ALTER ROLE manabills_user SET client_encoding TO 'utf8';
ALTER ROLE manabills_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE manabills_user SET default_transaction_deferrable TO on;
ALTER ROLE manabills_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE manabills_db TO manabills_user;
\q
EOF

psql -U manabills_user -d manabills_db -c "SELECT version();"
```

- [ ] Database created successfully
- [ ] Can connect as `manabills_user`

---

## Step 3: Update Django Settings

**File: `config/settings.py`**

Find this section:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'billing_db',
        'USER': 'billing_user',
        'PASSWORD': 'billing123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

Replace with:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'manabills_db',
        'USER': 'manabills_user',
        'PASSWORD': 'your_secure_password_123',  # ← UPDATE THIS!
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        },
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
    }
}
```

⚠️ **IMPORTANT**: Change password to your actual password!

- [ ] Settings updated
- [ ] Password matches database user password

---

## Step 4: Verify Files Were Updated

**Check that these files exist with optimizations:**

```bash
# Windows
ls -la business_billing\models.py
ls -la business_billing\views.py
ls -la business_billing\migrations\0001_enable_trgm.py

# Linux/Mac
ls -la business_billing/models.py
ls -la business_billing/views.py
ls -la business_billing/migrations/0001_enable_trgm.py
```

**Check model.py has GinIndex:**
```bash
grep -n "GinIndex" business_billing/models.py
```

**Check views.py has aggregate with filter:**
```bash
grep -n "aggregate(" business_billing/views.py
grep -n "filter=Q" business_billing/views.py
```

- [ ] models.py optimized (has GinIndex)
- [ ] views.py optimized (has aggregate with filters)
- [ ] Migration 0001_enable_trgm.py exists

---

## Step 5: Test Database Connection

```bash
python manage.py shell
>>> from django.db import connection
>>> connection.ensure_connection()
>>> print("✅ Connected to PostgreSQL!")
>>> exit()
```

- [ ] Database connection successful

---

## Step 6: Run Migrations (IN ORDER)

### 6a. Enable pg_trgm Extension FIRST

```bash
python manage.py migrate business_billing 0001_enable_trgm
```

**Expected output:**
```
Running migrations:
  Applying business_billing.0001_enable_trgm... OK
```

- [ ] pg_trgm migration applied

### 6b. Generate Model Migrations

```bash
python manage.py makemigrations business_billing
```

**Expected output:**
```
You are working with an old migration library; some features may not work:...
Migrations for 'business_billing':
  business_billing/migrations/0005_auto_20260410_1445.py
    - Alter field ... on shopprofile
    - Create index ... on product
    - Create index ... on invoice
    - ... (many index creations)
```

- [ ] Migrations generated successfully

### 6c. Apply All Migrations

```bash
python manage.py migrate
```

**Expected output:**
```
Running migrations:
  Applying accounts.0001_initial... OK
  Applying accounts.0002_remove_user_email_alter_user_mobile_number... OK
  ...
  Applying business_billing.0005_auto_20260410_1445... OK
  
Operations to perform:
  Apply all migrations: accounts, admin, auth, business_billing, ...
  
Your models in app(s): ... have changes that are not yet migrated.
```

- [ ] All migrations applied successfully
- [ ] No errors or failures

---

## Step 7: Verify Indexes Created

```bash
python manage.py dbshell
```

Then paste these PostgreSQL commands:

```sql
-- List all indexes on business_billing tables
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename LIKE 'bb_%'
ORDER BY tablename, indexname;

-- Verify trigram indexes
SELECT indexname FROM pg_indexes
WHERE indexname LIKE '%gin%' AND tablename LIKE 'bb_%';

-- Count total indexes
SELECT COUNT(*) as total_indexes
FROM pg_indexes
WHERE schemaname = 'public' AND tablename LIKE 'bb_%';

\q
```

**Expected output (15+ indexes):**
```
 schemaname |   tablename   |        indexname         
-------------+---------------+---------------------------
 public      | bb_customer   | customer_name_gin
 public      | bb_invoice    | invoice_balance_idx
 public      | bb_invoice    | invoice_custname_gin
 public      | bb_invoice    | invoice_gst_report_idx
 public      | bb_invoice    | invoice_user_created_idx
 public      | bb_invoice    | invoice_user_payment_idx
 public      | bb_invoice    | invoice_user_status_idx
 public      | bb_product    | product_low_stock_idx
 public      | bb_product    | product_med_expiry_idx
 public      | bb_product    | product_name_gin
 public      | bb_product    | product_user_active_idx
 public      | bb_product    | product_user_cat_idx
 public      | bb_shopprofile| shopprofile_user_gst_idx
 ...
```

- [ ] All 15+ indexes created
- [ ] GIN trigram indexes visible
- [ ] No errors

---

## Step 8: Create Test Data

```bash
python manage.py shell
```

```python
from accounts.models import User
from business_billing.models import Customer, Product, Invoice

# Create test user
user = User.objects.create_user(
    username='testshop',
    mobile_number='9999999999',
    password='testpass123'
)

# Create test customer
customer = Customer.objects.create(
    user=user,
    name='Test Customer',
    mobile='8888888888'
)

# Create test products
for i in range(5):
    Product.objects.create(
        user=user,
        name=f'Test Product {i+1}',
        selling_price=100 + i*50,
        qty=50 + i*10
    )

print("✅ Test data created!")
exit()
```

- [ ] Test data created

---

## Step 9: Test API Endpoints

```bash
python manage.py runserver
```

Then test these endpoints (use Postman or curl):

### 9a. Dashboard Stats
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/business/dashboard/
```

**Expected: Should return < 100ms**

- [ ] Dashboard endpoint works
- [ ] Returns all 12 KPI metrics
- [ ] Response time < 100ms

### 9b. Product Search (Autocomplete)
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/business/products/search/?q=Test&cat=all"
```

**Expected: Should return < 50ms**

- [ ] Product search works
- [ ] Returns matching products
- [ ] Response time < 50ms

### 9c. Invoice List
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/business/invoices/?status=All&payment=Cash"
```

**Expected: Quick response**

- [ ] Invoice list works
- [ ] Filters applied correctly

---

## Step 10: Monitor with Django Debug Toolbar (Optional)

Add to `config/settings.py`:
```python
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']
```

Add to `config/urls.py`:
```python
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
```

Install:
```bash
pip install django-debug-toolbar
```

Then visit http://localhost:8000/api/business/dashboard/ and check:
- **SQL tab**: Should show fewer queries (was 8, now ~2)
- **Execution time**: Should be < 50ms

- [ ] Debug toolbar installed (optional)
- [ ] Query count reduced from 8 to 2

---

## Step 11: Enable PostgreSQL Query Logging (Production)

**Edit PostgreSQL config:**

**Windows:** `C:\Program Files\PostgreSQL\15\data\postgresql.conf`  
**Linux:** `/var/lib/postgresql/15/main/postgresql.conf`

Find and uncomment:
```ini
log_min_duration_statement = 100  # Log queries slower than 100ms
log_statement = 'all'              # Log all statements
```

Restart PostgreSQL:
```bash
# Windows
net stop postgresql-x64-15
net start postgresql-x64-15

# Linux
sudo systemctl restart postgresql
```

Check logs:
```bash
# Windows
type "C:\Program Files\PostgreSQL\15\data\log\postgresql.log" | tail

# Linux
sudo tail -f /var/log/postgresql/postgresql.log
```

- [ ] Query logging enabled

---

## Step 12: Deploy to Production

```bash
# Build
python manage.py collectstatic --noinput

# Run tests
python manage.py test business_billing

# Deploy to production server with:
# 1. PostgreSQL database configured
# 2. All migrations applied
# 3. Django secret key from environment
```

- [ ] Tests pass
- [ ] collectstatic runs without errors
- [ ] Ready for production deploy

---

## Verification Checklist - Final

- [ ] PostgreSQL database created and accessible
- [ ] psycopg2-binary installed
- [ ] config/settings.py updated with correct credentials
- [ ] models.py has GinIndex and indexes
- [ ] views.py has optimized dashboard_stats
- [ ] migrations/0001_enable_trgm.py exists
- [ ] All migrations applied (migrate business_billing 0001_enable_trgm, then makemigrations, then migrate)
- [ ] 15+ indexes visible in PostgreSQL
- [ ] Test data created successfully
- [ ] API endpoints respond quickly (< 100ms)
- [ ] Dashboard stats returns all 12 metrics
- [ ] Product search works (< 50ms)
- [ ] No database errors in logs

---

## Troubleshooting

### Error: "psycopg2: command not found"
```bash
pip install psycopg2-binary
```

### Error: "FATAL: Ident authentication failed"
Update `pg_hba.conf` and restart PostgreSQL (see POSTGRESQL_SETUP.md)

### Error: "django.core.exceptions.ImproperlyConfigured"
Check `config/settings.py` DATABASE settings are correct

### Error: "Relation 'bb_invoice' does not exist"
Run: `python manage.py migrate business_billing 0001_enable_trgm` first

### Slow queries despite indexes
```bash
python manage.py dbshell
ANALYZE;  # Update query planner statistics
\q
```

---

## Success Indicators ✅

When deployment is complete, you should see:

1. **Dashboard loads in < 50ms** (vs ~200ms before)
2. **Product autocomplete < 10ms** (vs ~50ms before)
3. **Invoice list < 5ms** (vs ~30ms before)
4. **Database logs show GIN index usage** (gin_trgm_ops)
5. **Single aggregation query for dashboard** (instead of 6 queries)

---

**Date:** 2026-04-10  
**Status:** Ready for deployment  
**Next Step:** Follow Step 1 and proceed through checklist

Good luck! 🚀
