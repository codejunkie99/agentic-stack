# Analytical Frameworks

Generic consulting / analytical frameworks. All frameworks below are
firm-generic (Minto, Porter, McKinsey-attributed, or industry-standard) and
are useful across any analytical engagement — consulting work, personal
projects, strategy reviews.

BCG-attributed frameworks (Growth-Share Matrix and any other BCG-authored
content) live in `adapters/bcg/context/frameworks/` and load on top of
this generic base when the BCG adapter is enabled.

## Problem Structuring

### Issue Tree
Decompose a business question into MECE branches.
- Start with the root question
- Each branch is an independent contributor to the answer
- Decompose until branches are specific enough to analyze
- Test: sum of branches = complete answer; no branch overlaps another

### Pyramid Principle (Barbara Minto)
Structure communications with answer first.
- Governing thought at the top (the recommendation or key insight)
- Supporting arguments in the second level (3-5 maximum, MECE)
- Evidence at the third level (specific, quantified)
- Never bury the answer

### MECE (Mutually Exclusive, Collectively Exhaustive)
A test for analytical completeness:
- **Mutually Exclusive:** No overlap between categories
- **Collectively Exhaustive:** All possibilities are covered
- Apply to: frameworks, analysis buckets, options lists, workplans

## Strategy Frameworks

### 7-S Framework (McKinsey)
Seven interdependent organizational elements:
- **Hard:** Strategy, Structure, Systems
- **Soft:** Shared Values, Skills, Style, Staff
- Use for: organizational change, capability assessment, cultural diagnosis

### Pricing Strategy Framework
Three pricing approaches:
- **Cost-plus** — Price = cost + margin target
- **Competitive** — Price anchored to market (parity, premium, or discount)
- **Value-based** — Price = value delivered to customer

(For BCG's practice-specific recommendation on pricing-approach sequencing,
see `adapters/bcg/context/frameworks/bcg-matrix.md`.)

### Value Chain Analysis (Porter)
Decompose a business into primary and support activities:
- Primary: Inbound logistics, Operations, Outbound logistics, Marketing & Sales, Service
- Support: Firm infrastructure, HR, Technology, Procurement
- Use for: identifying cost reduction and differentiation opportunities

## Analytics Frameworks

### Driver Tree
Decompose a KPI into multiplicative or additive drivers.
- Root node = the KPI (e.g., revenue)
- Decompose: Revenue = Volume × Price, or by segment, product, channel
- Quantify each driver's contribution
- Use for: value sizing, performance diagnosis, prioritization

### Sensitivity Analysis
Test how conclusions change as inputs vary:
- Identify the top 3-5 most impactful input assumptions
- Test each ±20%, ±50%
- Report as: [Conclusion holds / changes] if [assumption] varies to [value]

### Market Sizing (Top-Down)
Estimate market size using macroeconomic data:
- Start with total addressable population or spend
- Apply segmentation filters
- Apply penetration rate
- Cross-check with bottom-up

### Market Sizing (Bottom-Up)
Estimate market size from unit economics:
- Estimate number of buyers
- Estimate purchase frequency
- Estimate average transaction value
- Multiply and cross-check with top-down
