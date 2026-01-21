# Supply-Chain Risk (Quantum tech)
Owner: Karl M. Kohler

## Scope
This module provides a first-order supply-chain risk assessment for quantum-technology components and segments. It is designed as an independent micro-service within OpenPolicyStack, returning a simple risk score, key drivers, and a short policy oriented brief for scenario analysis.

The MVP focuses on reproducibility and a clear interface rather than final data or models.

## Inputs (MVP)
•⁠  ⁠country_or_region  
  Target economy or region (e.g. EU, US, China).
•⁠  ⁠segment_or_component  
  Quantum-technology segment or component (e.g. cryogenics, photonics,
  ion-trap components, control electronics).
•⁠  ⁠optional: scenario  
  High-level disruption or policy scenario (e.g. export restriction,
  supplier disruption).
•⁠  ⁠optional: year / time window

## Outputs (MVP)
•⁠  ⁠risk_score  
  Relative risk score (0–100).
•⁠  ⁠risk_level  
  Categorical label (Low / Medium / High).
•⁠  ⁠key_drivers  
  Main contributing factors (e.g. supplier concentration,
  geo-exposure, regulatory risk).
•⁠  ⁠brief  
  Short text explanation suitable for a policy dashboard or demo.

## How to run (MVP)
Preferred interface:I chose API.

My MVP will expose a minimal API endpoint that takes (country_or_region, segment_or_component, optional scenario) and returns the outputs bove. Data sources and scoring logic will of course be refined in later phases.

## Example scenario
Input:
•⁠  ⁠country_or_region: EU
•⁠  ⁠segment_or_component: quantum cryogenic systems
•⁠  ⁠scenario: export restriction

Output:
•⁠  ⁠risk_score: 80
•⁠  ⁠risk_level: High
•⁠  ⁠key_drivers: supplier concentration, limited substitution, regulatory exposure
•⁠  ⁠brief: Short summary of vulnerabilities and potential mitigation options.
