// Student Ambassador Platform - Commons Graph Schema
// This schema defines the shared knowledge graph stored in FalkorDB

// =============================================================================
// NODE SCHEMAS
// =============================================================================

// School Node - Represents educational institutions
// Properties:
//   - id: Unique identifier (String)
//   - name: Institution name (String)
//   - type: Institution type - public, private, community (String)
//   - location: Geographic location - state or region (String)
//   - selectivity: Admission selectivity - highly_selective, selective, moderate, open (String)

// ScholarshipSource Node - Represents scholarship/grant opportunities
// Properties:
//   - id: Unique identifier (String)
//   - name: Scholarship name (String)
//   - amount_min: Minimum award amount (Float)
//   - amount_max: Maximum award amount (Float)
//   - criteria: Eligibility criteria description (String)
//   - deadline: Application deadline (Date)
//   - verified: Whether source has been verified (Boolean)
//   - url: Application URL (String)
//   - renewable: Whether scholarship is renewable (Boolean)

// AnonymizedProfile Node - Represents anonymized student profiles for pattern matching
// Properties:
//   - id: Anonymous identifier - no link to actual student (String)
//   - gpa_range: GPA bucket - "3.75-4.0", "3.5-3.75", etc. (String)
//   - test_range: Test score bucket - "1400-1500", etc. (String)
//   - income_bracket: Income category - low, middle, high (String)
//   - first_gen: First generation college student (Boolean)
//   - region: Geographic region - generalized (String)

// Strategy Node - Represents negotiation/appeal strategies
// Properties:
//   - id: Unique identifier (String)
//   - type: Strategy type - appeal, negotiation, application (String)
//   - description: Strategy description (String)
//   - success_rate: Historical success rate 0.0-1.0 (Float)
//   - sample_size: Number of data points (Integer)
//   - last_updated: Last update timestamp (DateTime)

// Outcome Node - Represents verified outcomes
// Properties:
//   - id: Unique identifier (String)
//   - type: Outcome type - scholarship_won, appeal_success, admission (String)
//   - amount: Dollar amount if applicable (Float)
//   - verified: Whether outcome was verified via disbursement (Boolean)
//   - timestamp: When outcome occurred (DateTime)

// BehaviorType Node - Represents institutional behavior patterns
// Properties:
//   - id: Unique identifier (String)
//   - pattern: Behavior pattern name (String)
//   - description: Pattern description (String)

// =============================================================================
// INDEX CREATION
// =============================================================================

// School indexes
CREATE INDEX FOR (s:School) ON (s.id);
CREATE INDEX FOR (s:School) ON (s.name);
CREATE INDEX FOR (s:School) ON (s.type);
CREATE INDEX FOR (s:School) ON (s.selectivity);

// ScholarshipSource indexes
CREATE INDEX FOR (ss:ScholarshipSource) ON (ss.id);
CREATE INDEX FOR (ss:ScholarshipSource) ON (ss.name);
CREATE INDEX FOR (ss:ScholarshipSource) ON (ss.deadline);
CREATE INDEX FOR (ss:ScholarshipSource) ON (ss.verified);

// AnonymizedProfile indexes
CREATE INDEX FOR (ap:AnonymizedProfile) ON (ap.id);
CREATE INDEX FOR (ap:AnonymizedProfile) ON (ap.gpa_range);
CREATE INDEX FOR (ap:AnonymizedProfile) ON (ap.income_bracket);

// Strategy indexes
CREATE INDEX FOR (st:Strategy) ON (st.id);
CREATE INDEX FOR (st:Strategy) ON (st.type);
CREATE INDEX FOR (st:Strategy) ON (st.success_rate);

// Outcome indexes
CREATE INDEX FOR (o:Outcome) ON (o.id);
CREATE INDEX FOR (o:Outcome) ON (o.type);
CREATE INDEX FOR (o:Outcome) ON (o.verified);

// BehaviorType indexes
CREATE INDEX FOR (bt:BehaviorType) ON (bt.id);
CREATE INDEX FOR (bt:BehaviorType) ON (bt.pattern);

// =============================================================================
// RELATIONSHIP TYPES
// =============================================================================

// (:AnonymizedProfile)-[:APPLIED_TO {status, timeline}]->(:School)
// (:AnonymizedProfile)-[:MATCHED_TO {score, reasons}]->(:ScholarshipSource)
// (:AnonymizedProfile)-[:RECEIVED]->(:Outcome)
// (:Strategy)-[:EFFECTIVE_FOR {success_rate, sample_size}]->(:AnonymizedProfile)
// (:Strategy)-[:TARGETS]->(:School)
// (:School)-[:EXHIBITS_BEHAVIOR {confidence, sample_size}]->(:BehaviorType)
// (:ScholarshipSource)-[:AWARDED_TO {year, amount}]->(:AnonymizedProfile)
