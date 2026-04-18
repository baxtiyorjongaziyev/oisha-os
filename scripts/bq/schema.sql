-- Oisha OS — long-term memory schema
-- Dataset: jonbranding-85662071-ea38e.oisha_memory (europe-west3)
-- Run: bq query --use_legacy_sql=false --project_id=jonbranding-85662071-ea38e < schema.sql

-- 1. Leads — AmoCRM lid snapshot (har 2 soatda upsert)
CREATE TABLE IF NOT EXISTS `jonbranding-85662071-ea38e.oisha_memory.leads` (
  lead_id INT64 NOT NULL,
  pipeline_id INT64,
  status_id INT64,
  stage STRING,
  name STRING,
  phone STRING,
  price NUMERIC,
  owner_id INT64,
  responsible_user_id INT64,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  closed_at TIMESTAMP,
  custom_fields JSON,
  fetched_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(fetched_at)
CLUSTER BY pipeline_id, status_id;

-- 2. Lead notes — AmoCRM izohlar
CREATE TABLE IF NOT EXISTS `jonbranding-85662071-ea38e.oisha_memory.lead_notes` (
  note_id INT64 NOT NULL,
  lead_id INT64 NOT NULL,
  note_type STRING,
  text STRING,
  created_at TIMESTAMP,
  created_by INT64,
  fetched_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY lead_id;

-- 3. Lead events — pipeline harakatlari (status o'zgarishlari)
CREATE TABLE IF NOT EXISTS `jonbranding-85662071-ea38e.oisha_memory.lead_events` (
  event_id STRING NOT NULL,
  lead_id INT64 NOT NULL,
  event_type STRING,
  from_status_id INT64,
  to_status_id INT64,
  changed_at TIMESTAMP NOT NULL,
  changed_by INT64,
  payload JSON,
  fetched_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(changed_at)
CLUSTER BY lead_id;

-- 4. Conversations — Telegram/WhatsApp xabarlar + embeddings
CREATE TABLE IF NOT EXISTS `jonbranding-85662071-ea38e.oisha_memory.conversations` (
  id STRING NOT NULL,
  platform STRING NOT NULL,
  chat_id INT64,
  lead_id INT64,
  user_id INT64,
  direction STRING,
  sender_name STRING,
  text STRING,
  text_len INT64,
  text_embedding ARRAY<FLOAT64>,
  embedded_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY lead_id, platform;

-- 5. Deals outcome — yutuq/yutqazish (training signal)
CREATE TABLE IF NOT EXISTS `jonbranding-85662071-ea38e.oisha_memory.deals_outcome` (
  lead_id INT64 NOT NULL,
  pipeline_id INT64,
  outcome STRING,
  won_amount NUMERIC,
  lost_reason STRING,
  cycle_days INT64,
  touches_count INT64,
  closed_at TIMESTAMP,
  labeled_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(closed_at)
CLUSTER BY outcome;

-- 6. Objections — aniqlangan e'tirozlar
CREATE TABLE IF NOT EXISTS `jonbranding-85662071-ea38e.oisha_memory.objections` (
  id STRING NOT NULL,
  lead_id INT64 NOT NULL,
  category STRING,
  raw_text STRING,
  handled BOOL,
  handled_at TIMESTAMP,
  detected_at TIMESTAMP NOT NULL,
  source_message_id STRING
)
PARTITION BY DATE(detected_at)
CLUSTER BY lead_id, category;

-- 7. AI responses — har AI chaqiruv natijasi (router audit trail)
CREATE TABLE IF NOT EXISTS `jonbranding-85662071-ea38e.oisha_memory.ai_responses` (
  id STRING NOT NULL,
  lead_id INT64,
  conversation_id STRING,
  task_type STRING NOT NULL,
  model STRING NOT NULL,
  prompt_hash STRING,
  prompt_preview STRING,
  response_preview STRING,
  tokens_in INT64,
  tokens_out INT64,
  cost_usd NUMERIC,
  latency_ms INT64,
  was_sent BOOL,
  was_approved BOOL,
  rejection_reason STRING,
  outcome_delta STRING,
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY task_type, model;
