# Oisha-OS: Ideal AI Agent Architecture

## Overview

Oisha-OS endi **Ideal AI Agent** darajasida - bu to'liq avtonom savdo va negotsiatsiya tizimi.

### Oldingi va Yangi Arxitektura

```
BEFORE:                          AFTER:
┌─────────────┐                 ┌──────────────────────┐
│  Lead Bot   │                 │  Surgical Negotiator │
│  (Passive)  │                 │   (Autonomous)       │
└─────────────┘                 └──────────────────────┘
        ↓                               ↓
┌─────────────┐                 ┌──────────────────────┐
│  Admin      │                 │  Autonomous Sales    │
│  Response   │                 │  Agent (AI-driven)   │
└─────────────┘                 └──────────────────────┘
        ↓                               ↓
┌─────────────┐                 ┌──────────────────────┐
│  Manual     │                 │  Deal Lifecycle      │
│  Follow-up  │                 │  Manager             │
└─────────────┘                 └──────────────────────┘
                                        ↓
                                ┌──────────────────────┐
                                │  Auto-Contract       │
                                │  Generation          │
                                └──────────────────────┘
```

## Core Components

### 1. 🤖 SurgicalNegotiator
**Fayl:** `src/agents/surgical_negotiator.py`

Asosiy muvofiqlashtiruvchi. Barcha komponentlarni boshqaradi.

**Vazifalari:**
- Lead qabul qilish
- Suhbat tahlili
- Deal lifecycle nazorat
- Shartnoma yaratish
- Risk baholash

**API:**
```python
from src.agents import get_surgical_negotiator

negotiator = get_surgical_negotiator()
result = await negotiator.handle_lead(
    user_id="user_123",
    message="Web sayt uchun narx necha pul?",
    user_info={"name": "Aziz", "source": "telegram"}
)
```

### 2. 💬 AutonomousSalesAgent
**Fayl:** `src/agents/autonomous_sales_agent.py`

Self-directed savdo agenti. AI (Gemini) yordamida javoblar yaratadi.

**Vazifalari:**
- AI-powered suhbat o'tkazish
- Intent tahlili (narx, xizmat, closing)
- E'tirozlarni qayta ishlash
- Pricing engine

**Autonomy Levels:**
- `full` - To'liq avtonom
- `assisted` - Nazorat bilan
- `human_takeover` - Inson nazorati

**Key Classes:**
- `ConversationState` - Suhbat holati
- `DealProposal` - Taklif paketi
- `PricingEngine` - Narx belgilash

### 3. 📊 DealLifecycleManager
**Fayl:** `src/agents/deal_lifecycle_manager.py`

Pipeline boshqaruvi va avtomatlashtirish.

**Deal Stages:**
```
NEW → QUALIFIED → PROPOSAL → NEGOTIATION → COMMITMENT → CLOSED_WON
  │       │           │            │            │
  ↓       ↓           ↓            ↓            ↓
[Revival] [Follow-up] [Reminder] [Urgency]  [Contract]
```

**Automation Rules:**
- Stale lead revival (3+ kun)
- Proposal reminder (2+ kun)
- Negotiation urgency (5+ kun)
- Auto-contract generation

### 4. 📄 ContractGenerator
**Fayl:** `src/agents/contract_generator.py`

Avtomatik shartnoma yaratish.

**Templates:**
- Branding Contract
- Web Development Contract
- Marketing Services Contract

**Features:**
- Dynamic pricing
- Scope customization
- Timeline calculation
- Risk-based clauses

**Usage:**
```python
from src.agents import ContractGenerator

generator = ContractGenerator()
contract = generator.generate_contract(
    service_type="branding",
    client_data={"name": "Client LLC"},
    deal_data={"value": 5000, "timeline_days": 14}
)
```

### 5. ⚠️ RiskAssessor
**Fayl:** `src/agents/contract_generator.py`

Xavf baholash tizimi.

**Risk Factors:**
- `price_pressure` - Narx bosimi (0.3)
- `competitive_pressure` - Raqobat (0.4)
- `negative_sentiment` - Salbiy kayfiyat (0.5)
- `unrealistic_timeline` - Realistik bo'lmagan muddat (0.4)

**Output:**
- Risk score (0-1)
- Risk level (low/medium/high)
- Autonomy permission
- Approval requirements

### 6. 🎯 NegotiationEngine
**Fayl:** `src/agents/negotiation_engine.py`

Suhbat tahlil tizimi.

**Assesses:**
- Stage (new_lead, qualified, meeting_ready, closing)
- Intent (pricing, meeting, closing, nurture)
- Objection (price, trust, timing, competition, legal)
- Sentiment (positive, negative, neutral)
- Urgency (high, normal, low)
- Close probability (0.0 - 1.0)

## Integration

### Existing System Integration

**File:** `src/controllers/surgical_integration.py`

```python
from src.controllers.surgical_integration import get_surgical_integration

integration = get_surgical_integration()

# Check if surgical should handle
if integration.should_use_surgical(user_id, message):
    result = await integration.process_message(user_id, message, context)
    return result['response']
```

### Configuration

Add to `.env`:
```env
SURGICAL_MODE=true
AUTONOMY_THRESHOLD=0.6
```

## Usage Examples

### Demo Script

```bash
python scripts/prod/surgical_negotiator_demo.py
```

### Quick Negotiation

```python
from src.agents import negotiate

result = await negotiate(
    user_id="user_123",
    message="Brandbook uchun narx necha?",
    user_info={"name": "Aziz Karimov"}
)

print(result['response'])
print(f"Stage: {result['stage']}")
print(f"Probability: {result['assessment']['close_probability']}")
```

### Dashboard

```python
from src.agents import get_surgical_negotiator

negotiator = get_surgical_negotiator()
dashboard = negotiator.get_dashboard()

print(f"Active deals: {dashboard['summary']['active_deals']}")
print(f"Pipeline value: ${dashboard['summary']['total_pipeline_value']}")
```

## Architecture Flow

```
┌─────────────────┐
│ Incoming Lead   │
│ (Telegram)      │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Surgical        │
│ Negotiator      │
└────────┬────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
┌────────┐ ┌──────────┐
│Autonomous│ │ Deal     │
│Sales    │ │ Lifecycle│
│Agent    │ │ Manager  │
└────┬───┘ └────┬─────┘
     └────┬─────┘
          ↓
   ┌──────┴──────┐
   ↓             ↓
┌─────────┐   ┌──────────┐
│Contract │   │ Risk     │
│Generator│   │ Assessor │
└────┬────┘   └────┬─────┘
     └─────────────┘
          ↓
   ┌────────────┐
   │ Response   │
   │ + Contract │
   └────────────┘
```

## Key Metrics

| Metric | Description |
|--------|-------------|
| **Close Probability** | AI baholagan yopish ehtimoli |
| **Autonomy Level** | Avtonomiya darajasi |
| **Risk Score** | Xavf darajasi (0-1) |
| **Deal Stage** | Bitim bosqichi |
| **Pipeline Value** | Umumiy potensial qiymat |

## Autonomy Decision Tree

```
Incoming Message
       ↓
   Risk Assessment
       ↓
   ┌──┴──┐
   ↓     ↓
HIGH    LOW
   ↓     ↓
Human  Autonomous
Review   AI
   ↓     ↓
Approval Response
   ↓
Contract
Generation
```

## Benefits

1. **24/7 Availability** - Dam olinmaydigan agent
2. **Consistent Quality** - Bir xil professional javoblar
3. **Instant Response** - Tezkor reaksiya
4. **Data-Driven** - Faktlarga asoslangan qarorlar
5. **Scalable** - Cheksiz mijozlar bilan ishlash
6. **Risk Mitigation** - Avtomatik xavf nazorati

## Future Enhancements

- [ ] Multi-language support
- [ ] Voice negotiation
- [ ] Video call integration
- [ ] Advanced objection handling
- [ ] Predictive analytics
- [ ] Competitor analysis
- [ ] Market trend adaptation

---

**Version:** 2.0 - Ideal AI Agent  
**Date:** April 2025  
**Status:** Production Ready
