-- Create ENUM types
CREATE TYPE service_category AS ENUM (
    'plumbing',
    'electrical',
    'cleaning',
    'painting',
    'carpentry',
    'landscaping',
    'hvac',
    'pest_control',
    'appliance_repair',
    'other'
);

CREATE TYPE recurrence_frequency AS ENUM (
    'daily',
    'weekly',
    'biweekly',
    'monthly'
);

CREATE TYPE notification_type AS ENUM (
    'new_job',
    'new_offer',
    'offer_accepted',
    'offer_rejected',
    'job_booked',
    'job_status_update',
    'new_message',
    'payment_received',
    'rating_received'
);

CREATE TYPE payment_method AS ENUM (
    'card',
    'wallet',
    'upi'
);

CREATE TYPE payment_status AS ENUM (
    'pending',
    'processing',
    'completed',
    'failed',
    'refunded'
);

CREATE TYPE job_status AS ENUM (
    'draft',
    'open',
    'negotiating',
    'booked',
    'en_route',
    'in_progress',
    'completed',
    'cancelled'
);

CREATE TYPE offer_status AS ENUM (
    'pending',
    'accepted',
    'rejected',
    'countered',
    'withdrawn'
);

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    role VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bio TEXT,
    service_categories VARCHAR(500),
    hourly_rate FLOAT,
    latitude FLOAT,
    longitude FLOAT,
    service_radius_km FLOAT,
    address VARCHAR(500)
);

CREATE INDEX ix_users_id ON users(id);
CREATE INDEX ix_users_email ON users(email);

-- Create job_templates table
CREATE TABLE job_templates (
    id SERIAL PRIMARY KEY,
    homeowner_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    service_category service_category NOT NULL,
    description TEXT NOT NULL,
    address VARCHAR(500) NOT NULL,
    estimated_hours FLOAT,
    base_quote FLOAT NOT NULL,
    is_recurring BOOLEAN NOT NULL,
    recurrence_frequency recurrence_frequency,
    next_scheduled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_job_templates_id ON job_templates(id);
CREATE INDEX ix_job_templates_homeowner_id ON job_templates(homeowner_id);

-- Create jobs table
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    homeowner_id INTEGER NOT NULL,
    provider_id INTEGER,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    service_category service_category NOT NULL,
    status job_status NOT NULL,
    address VARCHAR(500) NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    estimated_hours FLOAT,
    homeowner_quote FLOAT NOT NULL,
    final_price FLOAT,
    preferred_date TIMESTAMP,
    scheduled_at TIMESTAMP,
    template_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES job_templates(id),
    FOREIGN KEY (homeowner_id) REFERENCES users(id),
    FOREIGN KEY (provider_id) REFERENCES users(id)
);

CREATE INDEX ix_jobs_id ON jobs(id);
CREATE INDEX ix_jobs_homeowner_id ON jobs(homeowner_id);
CREATE INDEX ix_jobs_provider_id ON jobs(provider_id);

-- Create offers table
CREATE TABLE offers (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    proposed_price FLOAT NOT NULL,
    message TEXT,
    status offer_status NOT NULL,
    parent_offer_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (provider_id) REFERENCES users(id),
    FOREIGN KEY (parent_offer_id) REFERENCES offers(id)
);

CREATE INDEX ix_offers_id ON offers(id);
CREATE INDEX ix_offers_provider_id ON offers(provider_id);

-- Create messages table
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    is_read BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (sender_id) REFERENCES users(id),
    FOREIGN KEY (recipient_id) REFERENCES users(id)
);

CREATE INDEX ix_messages_id ON messages(id);
CREATE INDEX ix_messages_job_id ON messages(job_id);
CREATE INDEX ix_messages_sender_id ON messages(sender_id);
CREATE INDEX ix_messages_recipient_id ON messages(recipient_id);

-- Create payments table
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE,
    homeowner_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    amount FLOAT NOT NULL,
    method payment_method NOT NULL,
    status payment_status NOT NULL,
    transaction_ref VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (homeowner_id) REFERENCES users(id),
    FOREIGN KEY (provider_id) REFERENCES users(id)
);

CREATE INDEX ix_payments_id ON payments(id);
CREATE INDEX ix_payments_job_id ON payments(job_id);
CREATE INDEX ix_payments_homeowner_id ON payments(homeowner_id);
CREATE INDEX ix_payments_provider_id ON payments(provider_id);

-- Create ratings table
CREATE TABLE ratings (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE,
    rater_id INTEGER NOT NULL,
    ratee_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (rater_id) REFERENCES users(id),
    FOREIGN KEY (ratee_id) REFERENCES users(id)
);

CREATE INDEX ix_ratings_id ON ratings(id);
CREATE INDEX ix_ratings_job_id ON ratings(job_id);
CREATE INDEX ix_ratings_rater_id ON ratings(rater_id);
CREATE INDEX ix_ratings_ratee_id ON ratings(ratee_id);

-- Create notifications table
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type notification_type NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    is_read BOOLEAN NOT NULL,
    job_id INTEGER,
    offer_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (offer_id) REFERENCES offers(id)
);

CREATE INDEX ix_notifications_id ON notifications(id);
CREATE INDEX ix_notifications_user_id ON notifications(user_id);
