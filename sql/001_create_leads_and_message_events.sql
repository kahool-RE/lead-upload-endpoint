CREATE TABLE IF NOT EXISTS leads (
    id BIGSERIAL PRIMARY KEY,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(10),
    zip VARCHAR(20),
    status VARCHAR(50) NOT NULL,
    price NUMERIC(14,2),
    property_type VARCHAR(100),
    dom INTEGER,
    phone VARCHAR(50),
    email VARCHAR(255),
    owner_name VARCHAR(255),
    owner_occupied BOOLEAN NOT NULL DEFAULT FALSE,
    score INTEGER NOT NULL DEFAULT 0,
    outreach_status VARCHAR(50) NOT NULL DEFAULT 'new',
    do_not_contact BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_leads_city ON leads (city);
CREATE INDEX IF NOT EXISTS ix_leads_state ON leads (state);
CREATE INDEX IF NOT EXISTS ix_leads_zip ON leads (zip);
CREATE INDEX IF NOT EXISTS ix_leads_status ON leads (status);
CREATE INDEX IF NOT EXISTS ix_leads_property_type ON leads (property_type);
CREATE INDEX IF NOT EXISTS ix_leads_dom ON leads (dom);
CREATE INDEX IF NOT EXISTS ix_leads_phone ON leads (phone);
CREATE INDEX IF NOT EXISTS ix_leads_email ON leads (email);
CREATE INDEX IF NOT EXISTS ix_leads_score ON leads (score);
CREATE INDEX IF NOT EXISTS ix_leads_outreach_status ON leads (outreach_status);
CREATE INDEX IF NOT EXISTS ix_leads_do_not_contact ON leads (do_not_contact);
CREATE INDEX IF NOT EXISTS ix_leads_address_city_state_zip ON leads (address, city, state, zip);
CREATE INDEX IF NOT EXISTS ix_leads_outreach_status_score ON leads (outreach_status, score);

CREATE TABLE IF NOT EXISTS message_events (
    id BIGSERIAL PRIMARY KEY,
    lead_id BIGINT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    message_body TEXT NOT NULL,
    sent_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'queued'
);

CREATE INDEX IF NOT EXISTS ix_message_events_lead_id ON message_events (lead_id);
CREATE INDEX IF NOT EXISTS ix_message_events_channel ON message_events (channel);
CREATE INDEX IF NOT EXISTS ix_message_events_direction ON message_events (direction);
CREATE INDEX IF NOT EXISTS ix_message_events_sent_at ON message_events (sent_at);
CREATE INDEX IF NOT EXISTS ix_message_events_received_at ON message_events (received_at);
CREATE INDEX IF NOT EXISTS ix_message_events_status ON message_events (status);
CREATE INDEX IF NOT EXISTS ix_message_events_lead_channel_direction ON message_events (lead_id, channel, direction);
