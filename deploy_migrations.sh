#!/usr/bin/env bash
# ManaBills PostgreSQL Migration Quick Commands

echo "=========================================="
echo "ManaBills PostgreSQL Optimization Deploy"
echo "=========================================="
echo ""

# Step 1: Enable pg_trgm extension
echo "Step 1: Enabling PostgreSQL pg_trgm extension..."
python manage.py migrate business_billing 0001_enable_trgm

if [ $? -ne 0 ]; then
    echo "❌ Migration failed! Check your database connection."
    exit 1
fi

echo "✅ pg_trgm extension enabled"
echo ""

# Step 2: Generate new migrations for optimized models
echo "Step 2: Generating migrations for optimized models..."
python manage.py makemigrations business_billing

if [ $? -ne 0 ]; then
    echo "❌ Migration generation failed!"
    exit 1
fi

echo "✅ Migrations generated"
echo ""

# Step 3: Apply all migrations
echo "Step 3: Applying all migrations..."
python manage.py migrate

if [ $? -ne 0 ]; then
    echo "❌ Migration application failed!"
    exit 1
fi

echo "✅ All migrations applied successfully"
echo ""

# Step 4: Verification
echo "Step 4: Verifying indexes..."
python manage.py dbshell << EOF
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename LIKE 'bb_%'
ORDER BY tablename, indexname;
EOF

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test product search endpoint"
echo "2. Monitor dashboard load time"
echo "3. Check PostgreSQL logs for slow queries"
echo ""
