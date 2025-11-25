# Semantic Data Model Questions for the ND Oil and Well Demo Production Data

This set of questions is designed to exercise the SQL system with the Semantic Data Model for the ND Oil and Well Demo Production Data included with Studio by default. It will showcase the capabilities of the SQL system and the Semantic Data Model.

## Busines Context used during Semantic Data Model Creation

> Operational and analytical model of North Dakota oil and gas well production, sourced from the NDIC Oil & Gas Division monthly and annual production reports. Contains state-reported well-level monthly production totals in gallons (oil, gas, water), days on production, cumulative volumes, and regulatory identifiers (API and file numbers) linked to operator, field/pool, county, and TRS legal location, supporting regulatory reporting, production trending, operator benchmarking, flaring analysis, and geospatial queries by well and time period.

## Exercise Questions

### Base Question

1. What are the top 5 performing wells?

### Core production and ranking

1. For the latest available month, which operators had the top 10 total oil produced, and what were their average producing days and average GOR (gas produced per barrel of oil)?
1. Show the top 15 fields by oil produced last month versus the prior month, including absolute and percent change, ranked by percent change.
1. Over the last 12 months, which five counties had the highest cumulative oil sold, and what share of state total did each contribute?

### Time series and window functions

1. For each operator, compute month‑over‑month oil production change for the last 18 months, and flag months where the change exceeded ±10% (use LAG and window partitions).
1. For each well, calculate a 3‑month rolling average of oil produced and identify wells with three consecutive increases (rolling window + boolean streak logic).
1. Return the monthly state‑level GOR trend for the last 24 months and highlight months setting new record highs (running MAX over time).

### Gas capture and flaring analysis

1. For the last 6 months, which operators maintained gas capture of at least 95% in every month? Return gas_produced, gas_sold, flared volumes, and capture rate per month.
1. Identify wells with flaring intensity above 10% (gas_flared / gas_produced) for 2+ consecutive months in the last year; list operator, field, and months affected.
1. Which pools (reservoirs) had the highest total flared gas last quarter, and what was the average capture rate by pool?

### Quality, reconciliation, and anomaly checks

1. Compare the primary and archive production tables for the most recent 3 months and list any (api_well_number, month) pairs where oil_produced or gas_sold differ by more than 1%.
1. Find wells where oil_sold_bbl exceeds oil_produced_bbl by more than 5% in a month; show the preceding and following month for the same well to help diagnose timing effects.
1. List wells reporting fewer than 10 producing days but more than 5,000 bbl oil sold in the same month; include operator and field.

### Geospatial (PLSS/TRS) and area filters

1. Within Township 151 North, Range 101 West, which section-quarter combinations had the highest total oil produced year‑to‑date? Return section, quarter, and totals.
1. For McKenzie (MCK) and Williams (WIL) counties, compare monthly oil production trends for the last 12 months, including 3‑month moving averages by county.

### Operator benchmarking and cohorting

1. Rank operators by year‑to‑date oil per producing day per well (normalize by well‑days), and provide the top 10 with count of active wells and median producing days.
1. Among operators with at least 50 active wells in the past 6 months, which achieved the largest improvement in gas capture rate versus the prior 6 months?

### Transcripts join (context + quant)

1. For months where statewide oil production dropped more than 1% month‑over‑month, return the month, the contribution to the drop by county, and a 300‑character snippet from the Director’s Cut transcript mentioning weather, maintenance, or midstream events.
1. Extract months where gas capture improved by ≥1 percentage point month‑over‑month and return a transcript snippet explaining potential causes (e.g., new connections, maintenance completion).

### Complex, multi‑step diagnostic (join, window, anomaly, text mining)

1. Identify the top 20 “anomalous” months in the last 24 months where a well’s oil_sold deviated from its 6‑month rolling mean by more than 2 standard deviations, after requiring ≥20 producing days that month. For each anomaly: include well/field/operator, oil_produced, oil_sold, producing_days, flared gas, capture rate, the well’s prior and next month values (via LAG/LEAD), and attach a Director’s Cut transcript snippet for that reporting month that mentions outages, weather, pipeline maintenance, or price shocks (keyword match). Return rows labeled as Potential Timing, Potential Shut‑In/Restart, Potential Midstream Constraint, or Other based on rules you define in SQL CASE logic.
