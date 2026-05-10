# Remaining Router Conversions

## Routers Still Needing Conversion

### 1. messages.py
Simple router for message creation and listing. Follow this pattern:

```python
# List messages for a job
sql = "SELECT * FROM messages WHERE job_id = %s ORDER BY created_at DESC"
messages = db.query_all(sql, (job_id,))

# Create message
sql = """
    INSERT INTO messages (job_id, sender_id, recipient_id, content, is_read)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING *
"""
message = db.query_one(sql, (job_id, sender_id, recipient_id, content, False))

# Mark as read
sql = "UPDATE messages SET is_read = true WHERE id = %s AND recipient_id = %s"
db.execute(sql, (message_id, current_user['id']))
```

### 2. payments.py
Handles payment creation and listing:

```python
# Get payment
sql = "SELECT * FROM payments WHERE id = %s"
payment = db.query_one(sql, (payment_id,))

# Create payment
sql = """
    INSERT INTO payments (job_id, homeowner_id, provider_id, amount, method, status)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING *
"""
payment = db.query_one(sql, (...))

# Update payment status
sql = "UPDATE payments SET status = %s, completed_at = NOW() WHERE id = %s RETURNING *"
payment = db.query_one(sql, (new_status, payment_id))
```

### 3. ratings.py
Similar pattern - create, list, delete ratings:

```python
# Create rating
sql = """
    INSERT INTO ratings (job_id, rater_id, ratee_id, score, comment)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING *
"""

# Get average rating for user
sql = "SELECT AVG(score)::numeric, COUNT(*) FROM ratings WHERE ratee_id = %s"
result = db.query_one(sql, (user_id,))

# Delete rating
sql = "DELETE FROM ratings WHERE id = %s"
db.execute(sql, (rating_id,))
```

### 4. quotes.py
Job template management:

```python
# Create template
sql = """
    INSERT INTO job_templates (homeowner_id, name, service_category, description, ...)
    VALUES (%s, %s, %s, %s, ...)
    RETURNING *
"""

# List user's templates
sql = "SELECT * FROM job_templates WHERE homeowner_id = %s ORDER BY created_at DESC"
templates = db.query_all(sql, (homeowner_id,))

# Delete template
sql = "DELETE FROM job_templates WHERE id = %s AND homeowner_id = %s"
db.execute(sql, (template_id, homeowner_id))
```

### 5. recurring.py
Recurring job scheduling:

```python
# List recurring jobs
sql = """
    SELECT * FROM job_templates
    WHERE homeowner_id = %s AND is_recurring = true
    ORDER BY next_scheduled_at
"""
recurring = db.query_all(sql, (homeowner_id,))

# Update next scheduled date
sql = "UPDATE job_templates SET next_scheduled_at = %s WHERE id = %s"
db.execute(sql, (next_date, template_id))
```

### 6. notifications.py
Notification retrieval and status updates:

```python
# List user's notifications
sql = """
    SELECT * FROM notifications
    WHERE user_id = %s
    ORDER BY created_at DESC
    LIMIT %s OFFSET %s
"""
notifications = db.query_all(sql, (user_id, limit, skip))

# Mark as read
sql = "UPDATE notifications SET is_read = true WHERE id = %s AND user_id = %s"
db.execute(sql, (notif_id, user_id))

# Mark all as read
sql = "UPDATE notifications SET is_read = true WHERE user_id = %s"
db.execute(sql, (user_id,))
```

### 7. admin.py (Most Complex)
200+ lines. Key patterns:

```python
# Count with filters
sql = "SELECT COUNT(*) as count FROM jobs WHERE status = %s"
result = db.query_one(sql, (status,))
count = result['count']

# Aggregations
sql = "SELECT SUM(amount)::numeric as total, COUNT(*) FROM payments WHERE status = %s"
result = db.query_one(sql, (PaymentStatus.completed.value,))

# Complex joins (if needed)
sql = """
    SELECT u.*, COUNT(DISTINCT j.id) as job_count, SUM(p.amount)::numeric as total_earned
    FROM users u
    LEFT JOIN jobs j ON u.id = j.provider_id
    LEFT JOIN payments p ON j.id = p.job_id AND p.status = %s
    WHERE u.role LIKE %s
    GROUP BY u.id
    ORDER BY total_earned DESC
"""
results = db.query_all(sql, (PaymentStatus.completed.value, '%provider%'))
```

## Tips for Conversion

1. **Replace `db.query(Model).filter(...).all()` with:**
   ```python
   sql = "SELECT * FROM table WHERE condition = %s"
   results = db.query_all(sql, params)
   ```

2. **Replace `db.get(Model, id)` with:**
   ```python
   sql = "SELECT * FROM table WHERE id = %s"
   result = db.query_one(sql, (id,))
   ```

3. **Replace ORM relationships access with separate queries:**
   ```python
   # Old: job.offers (ORM relationship)
   # New:
   sql = "SELECT * FROM offers WHERE job_id = %s"
   offers = db.query_all(sql, (job_id,))
   ```

4. **For enums, always use `.value`:**
   ```python
   JobStatus.open.value  # "open"
   PaymentMethod.card.value  # "card"
   ```

5. **Access dict fields with bracket notation:**
   ```python
   result['id']  # not result.id
   user['email']  # not user.email
   ```

6. **For LIKE queries (contains):**
   ```python
   # Old: User.role.contains("provider")
   # New:
   sql = "SELECT * FROM users WHERE role LIKE %s"
   db.query_all(sql, ('%provider%',))
   ```

7. **For IN queries:**
   ```python
   # Old: Job.status.in_([status1, status2])
   # New:
   sql = "SELECT * FROM jobs WHERE status IN (%s, %s)"
   db.query_all(sql, (status1.value, status2.value))
   ```

8. **For transactions (multi-step operations):**
   ```python
   queries = [
       ("UPDATE jobs SET status = %s WHERE id = %s", (new_status, job_id)),
       ("INSERT INTO notifications ...", (user_id, ...)),
   ]
   db.execute_many(queries)
   ```

## Performance Gains

Native SQL conversions typically show:
- **2-5x faster** for simple queries
- **5-10x faster** for complex aggregations
- **Lower memory** usage (no ORM tracking)
- **More predictable** performance

## Testing Checklist

For each converted router:
- [ ] POST requests work (create operations)
- [ ] GET requests work (read operations)
- [ ] PATCH requests work (update operations)
- [ ] DELETE requests work (delete operations)
- [ ] Filters/parameters work correctly
- [ ] Pagination works (if applicable)
- [ ] Proper error codes returned
- [ ] Data integrity maintained

Good luck! You're almost there! 🚀
