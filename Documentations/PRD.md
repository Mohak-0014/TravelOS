# TravelOS — Product Requirements Document (PRD)

> **Version:** 1.0 · **Date:** June 2025 · **Status:** Active Development
> **Type:** Placement portfolio flagship — deployable & demoable, non-commercial
> **Owner:** Mohak

---

## 1. Executive Summary

TravelOS is a **stateful, AI-native travel orchestration platform** built on LangGraph and LangChain. Unlike traditional itinerary generators that produce a one-time static plan, TravelOS acts as a persistent *operating system* for a trip: it continuously maintains, adapts, validates, and optimizes the travel experience through coordinated multi-agent workflows.

The core emotional promise is simple:

> *"It knew my travel style."* and *"It planned everything."*

This document defines the product vision, target users, scope, and success criteria for the MVP. It is the **what and why**; the technical *how* lives in [`spec.md`](./spec.md).

---

## 2. Problem Statement

### 2.1 Current Pain Points

- Static itinerary tools break the moment reality diverges from the plan (rain, closures, delays).
- No memory across trips — users re-explain their preferences every single time.
- Budget tracking is disconnected from the itinerary, so overspend is discovered too late.
- Travelers juggle 5+ apps for weather, maps, hotels, restaurants, and visa rules.

### 2.2 The Opportunity

The deeper opportunity is not travel planning alone. It is demonstrating a **persistent, AI-native personal orchestration system** that coordinates long-horizon human activities using stateful multi-agent workflows — a portfolio-grade proof that I can design and ship complex agentic systems end to end.

---

## 3. Goals & Non-Goals

### 3.1 Goals (MVP)

1. Generate a coherent, personalized, day-by-day itinerary from a simple trip brief.
2. Ground every recommendation in **real, live data** (no mock data, no hallucinated hotels).
3. Adapt the itinerary dynamically when weather changes — with human approval.
4. Maintain user travel preferences across sessions (persistent memory).
5. Deploy a working, demoable instance on AWS free tier.

### 3.2 Non-Goals (v1)

- Payment processing or taking commission (booking redirects to provider).
- Flight search and booking.
- Native mobile apps (web-first; mobile is a future phase).
- Group coordination, visa automation, and local-events injection (documented as future phases).

---

## 4. Target Users & Personas

| Persona | Profile | Primary Need | Key Pain Point |
|---|---|---|---|
| **First-Time International Traveler** | Age 22–30, first trip abroad. Unsure about visas, customs, currency. | End-to-end hand-holding in one place. | Information overload; doesn't know what she doesn't know. |
| **Family Coordinator** | Parent, 35–50, planning for 2+ adults & 1–3 kids. Budget-conscious. | Balance preferences; child-friendly options; strict budget. | Manual consensus; surprise cost overruns. |
| **Luxury Traveler** | High-income professional, 35–55, 4+ trips/year. | Hyper-personalized, curated recommendations. Efficiency. | Generic suggestions that ignore his taste and history. |

**Primary persona for MVP:** First-Time International Traveler (highest need for an all-in-one orchestrator).

---

## 5. User Stories (MVP)

- As a traveler, I can create a trip by entering destination, dates, travelers, and budget, so I get a starting plan in seconds.
- As a traveler, I receive a day-by-day itinerary that minimizes backtracking and respects opening hours and meal times.
- As a traveler, I get real hotel options ranked to my budget and style, with live prices.
- As a traveler, when rain is forecast, the system proposes indoor alternatives and asks me to approve before changing anything.
- As a returning traveler, the system already knows my pace, food preferences, and budget behavior.
- As a traveler, I can ask the AI Concierge any question about my trip in natural language.

---

## 6. Core Features & Scope

### 6.1 MVP Features (Phases 1–4)

- **AI Itinerary Generation** — geographically coherent, pacing-optimized, weather-aware day plans.
- **Hotel Recommendations** — real live rates (LiteAPI), ranked by budget tier and travel style.
- **Restaurant Discovery** — Foursquare-sourced, filtered by cuisine, dietary needs, and proximity.
- **Weather-Aware Replanning** — Open-Meteo monitoring; indoor/outdoor swaps via approval gate.
- **AI Concierge Chat** — natural-language Q&A over the live trip state.
- **Persistent Travel Memory** — preferences remembered across trips (semantic + SQL).
- **Human-in-the-Loop Approvals** — user approves consequential changes before they apply.

### 6.2 Future Phases (documented, not built in v1)

- Group Coordination Agent · Visa Guidance Agent · Local Events Agent · Transport Coordination Agent · Budget Optimization Agent (basic budget tracking is in MVP; full optimization agent is phase 5).

---

## 7. Success Metrics

| Metric | Definition | MVP Target | v1.0 Target |
|---|---|---|---|
| Itinerary Generation Latency | Trip submit → first itinerary shown | < 10 s | < 5 s |
| Replanning Latency | Weather trigger → proposal surfaced | < 15 s | < 8 s |
| Concierge Response Time (P95) | Chat message → response | < 4 s | < 2 s |
| Recommendation Relevance | % of recs rated 4★+ in feedback | > 60% | > 80% |
| Data Grounding | % of recommendations backed by a real API result (no hallucinated venues) | 100% | 100% |
| Approval Acceptance Rate | % of AI proposals accepted unmodified | > 55% | > 75% |
| Test Coverage | % of backend agent/tool logic covered by tests | > 80% | > 90% |
| Agent Failure Rate | % of graph runs with ≥1 agent failure | < 5% | < 1% |

**Definition of Done (MVP):** A user can create a trip for a real city, receive a grounded multi-day itinerary with real hotels and restaurants, trigger a weather-based replan with approval, and have preferences persist to a second trip — all running on a deployed AWS free-tier instance, with > 80% test coverage.

---

## 8. Product Principles

1. **Persistent, not stateless** — every interaction builds on the user's travel history.
2. **Human trust first** — AI proposes; the user approves consequential changes.
3. **Continuous adaptation** — the itinerary is a living document, not a printout.
4. **Grounded recommendations** — all suggestions are retrieval-grounded; no invented venues.
5. **Graceful degradation** — on tool/agent failure, fall back to the last good checkpoint, never a blank screen.

---

## 9. MVP Roadmap

| Phase | Name | Key Deliverables | Est. |
|---|---|---|---|
| 1 | Basic Planner + CRUD | Auth, trip creation, static itinerary, hotel/restaurant fetch, base UI | 4 wks |
| 2 | Multi-Agent Orchestration | LangGraph Supervisor + 6 agents, approval system, tool integrations | 6 wks |
| 3 | Memory + Personalization | Semantic memory (Qdrant), preference embeddings, cross-trip personalization | 4 wks |
| 4 | Dynamic Replanning | Weather Adaptation Agent, event-driven replan loop, basic budget tracking | 4 wks |
| 5 (future) | Expansion | Group coordination, visa, events, transport, full budget optimization | TBD |

---

## 10. Open Questions & Assumptions

### Open Questions
- Monetization is out of scope (portfolio project) — but if demoed, do we show a "book on provider" redirect for realism? *(Leaning yes.)*
- Map rendering: Leaflet + OSM (free) confirmed; revisit if interaction needs exceed OSM tile limits.

### Assumptions
- Free-tier API quotas (LiteAPI, Open-Meteo, Foursquare, OpenTripMap, Ticketmaster) are sufficient for demo load.
- LangGraph is the right tool for stateful multi-agent orchestration at this scale.
- Single-region AWS free-tier deployment is acceptable for v1; multi-region is post-v1.
- Embeddings run locally via `sentence-transformers` to avoid paid embedding APIs.

---

*This PRD is a living document. The technical contract lives in `spec.md`; operational guardrails live in `GUARDRAILS.md`.*
