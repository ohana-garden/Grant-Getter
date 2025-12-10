// Student Ambassador Platform - Seed Data
// Sample data for development and testing

// =============================================================================
// SAMPLE SCHOOLS
// =============================================================================

// Highly Selective Schools
CREATE (s1:School {
    id: 'school_stanford',
    name: 'Stanford University',
    type: 'private',
    location: 'California',
    selectivity: 'highly_selective'
});

CREATE (s2:School {
    id: 'school_mit',
    name: 'Massachusetts Institute of Technology',
    type: 'private',
    location: 'Massachusetts',
    selectivity: 'highly_selective'
});

CREATE (s3:School {
    id: 'school_harvard',
    name: 'Harvard University',
    type: 'private',
    location: 'Massachusetts',
    selectivity: 'highly_selective'
});

// Selective Schools
CREATE (s4:School {
    id: 'school_ucla',
    name: 'University of California, Los Angeles',
    type: 'public',
    location: 'California',
    selectivity: 'selective'
});

CREATE (s5:School {
    id: 'school_umich',
    name: 'University of Michigan',
    type: 'public',
    location: 'Michigan',
    selectivity: 'selective'
});

CREATE (s6:School {
    id: 'school_usc',
    name: 'University of Southern California',
    type: 'private',
    location: 'California',
    selectivity: 'selective'
});

// Moderate Selectivity Schools
CREATE (s7:School {
    id: 'school_asu',
    name: 'Arizona State University',
    type: 'public',
    location: 'Arizona',
    selectivity: 'moderate'
});

CREATE (s8:School {
    id: 'school_osu',
    name: 'Ohio State University',
    type: 'public',
    location: 'Ohio',
    selectivity: 'moderate'
});

// Community Colleges
CREATE (s9:School {
    id: 'school_smcc',
    name: 'Santa Monica College',
    type: 'community',
    location: 'California',
    selectivity: 'open'
});

CREATE (s10:School {
    id: 'school_mcc',
    name: 'Miami Dade College',
    type: 'community',
    location: 'Florida',
    selectivity: 'open'
});

// =============================================================================
// SAMPLE SCHOLARSHIP SOURCES
// =============================================================================

// National Scholarships
CREATE (ss1:ScholarshipSource {
    id: 'scholarship_gates',
    name: 'Gates Scholarship',
    amount_min: 50000.0,
    amount_max: 300000.0,
    criteria: 'Outstanding minority students with significant financial need, demonstrated leadership, and academic excellence',
    deadline: date('2025-09-15'),
    verified: true,
    url: 'https://www.thegatesscholarship.org/',
    renewable: true
});

CREATE (ss2:ScholarshipSource {
    id: 'scholarship_coca_cola',
    name: 'Coca-Cola Scholars Program',
    amount_min: 20000.0,
    amount_max: 20000.0,
    criteria: 'High school seniors with leadership, academics, and community service',
    deadline: date('2025-10-31'),
    verified: true,
    url: 'https://www.coca-colascholarsfoundation.org/',
    renewable: false
});

CREATE (ss3:ScholarshipSource {
    id: 'scholarship_dell',
    name: 'Dell Scholars Program',
    amount_min: 20000.0,
    amount_max: 20000.0,
    criteria: 'Students who have overcome significant obstacles, Pell Grant eligible',
    deadline: date('2025-12-01'),
    verified: true,
    url: 'https://www.dellscholars.org/',
    renewable: false
});

CREATE (ss4:ScholarshipSource {
    id: 'scholarship_horatio_alger',
    name: 'Horatio Alger Scholarship',
    amount_min: 25000.0,
    amount_max: 25000.0,
    criteria: 'Students who have faced and overcome significant adversity',
    deadline: date('2025-10-25'),
    verified: true,
    url: 'https://scholars.horatioalger.org/',
    renewable: false
});

// STEM Scholarships
CREATE (ss5:ScholarshipSource {
    id: 'scholarship_nsf',
    name: 'NSF Graduate Research Fellowship',
    amount_min: 37000.0,
    amount_max: 111000.0,
    criteria: 'Graduate students in STEM fields with research potential',
    deadline: date('2025-10-21'),
    verified: true,
    url: 'https://www.nsfgrfp.org/',
    renewable: true
});

CREATE (ss6:ScholarshipSource {
    id: 'scholarship_goldwater',
    name: 'Barry Goldwater Scholarship',
    amount_min: 7500.0,
    amount_max: 7500.0,
    criteria: 'Sophomore and junior STEM students planning research careers',
    deadline: date('2026-01-24'),
    verified: true,
    url: 'https://goldwaterscholarship.gov/',
    renewable: true
});

// First-Generation Scholarships
CREATE (ss7:ScholarshipSource {
    id: 'scholarship_questbridge',
    name: 'QuestBridge National College Match',
    amount_min: 200000.0,
    amount_max: 300000.0,
    criteria: 'High-achieving, low-income high school seniors',
    deadline: date('2025-09-26'),
    verified: true,
    url: 'https://www.questbridge.org/',
    renewable: true
});

CREATE (ss8:ScholarshipSource {
    id: 'scholarship_first_gen',
    name: 'First Generation College Student Scholarship',
    amount_min: 5000.0,
    amount_max: 10000.0,
    criteria: 'First-generation college students with financial need',
    deadline: date('2025-12-15'),
    verified: true,
    url: 'https://firstgen.naspa.org/',
    renewable: true
});

// Local/Regional Scholarships
CREATE (ss9:ScholarshipSource {
    id: 'scholarship_rotary',
    name: 'Rotary Club Scholarship',
    amount_min: 1000.0,
    amount_max: 5000.0,
    criteria: 'Local students demonstrating community service',
    deadline: date('2026-03-01'),
    verified: true,
    url: 'https://www.rotary.org/',
    renewable: false
});

CREATE (ss10:ScholarshipSource {
    id: 'scholarship_community_foundation',
    name: 'Community Foundation Scholarship',
    amount_min: 2500.0,
    amount_max: 10000.0,
    criteria: 'Students attending college in their home state',
    deadline: date('2026-02-15'),
    verified: true,
    url: 'https://www.communityfoundation.org/',
    renewable: true
});

// =============================================================================
// SAMPLE BEHAVIOR TYPES
// =============================================================================

CREATE (bt1:BehaviorType {
    id: 'behavior_competes_offers',
    pattern: 'negotiates_with_competing_offers',
    description: 'School is known to match or increase aid when presented with competing offers from peer institutions'
});

CREATE (bt2:BehaviorType {
    id: 'behavior_appeals_friendly',
    pattern: 'appeals_friendly',
    description: 'School has a formal appeals process and frequently grants increases'
});

CREATE (bt3:BehaviorType {
    id: 'behavior_appeals_resistant',
    pattern: 'appeals_resistant',
    description: 'School rarely adjusts initial aid offers regardless of circumstances'
});

CREATE (bt4:BehaviorType {
    id: 'behavior_merit_focused',
    pattern: 'merit_focused',
    description: 'School prioritizes merit-based aid over need-based aid'
});

CREATE (bt5:BehaviorType {
    id: 'behavior_need_blind',
    pattern: 'need_blind_admission',
    description: 'School does not consider financial need in admission decisions'
});

CREATE (bt6:BehaviorType {
    id: 'behavior_meets_full_need',
    pattern: 'meets_full_demonstrated_need',
    description: 'School commits to meeting 100% of demonstrated financial need'
});

// =============================================================================
// SAMPLE STRATEGIES
// =============================================================================

CREATE (st1:Strategy {
    id: 'strategy_competing_offer',
    type: 'negotiation',
    description: 'Present competing offer from peer institution to request aid match',
    success_rate: 0.45,
    sample_size: 1250,
    last_updated: datetime('2024-12-01T00:00:00Z')
});

CREATE (st2:Strategy {
    id: 'strategy_special_circumstances',
    type: 'appeal',
    description: 'Appeal based on special circumstances not reflected in FAFSA (job loss, medical expenses, etc.)',
    success_rate: 0.62,
    sample_size: 890,
    last_updated: datetime('2024-12-01T00:00:00Z')
});

CREATE (st3:Strategy {
    id: 'strategy_merit_evidence',
    type: 'appeal',
    description: 'Provide additional evidence of merit achievements after initial application',
    success_rate: 0.38,
    sample_size: 456,
    last_updated: datetime('2024-12-01T00:00:00Z')
});

CREATE (st4:Strategy {
    id: 'strategy_demonstrated_interest',
    type: 'application',
    description: 'Demonstrate strong interest through campus visits, interviews, and engagement',
    success_rate: 0.72,
    sample_size: 2100,
    last_updated: datetime('2024-12-01T00:00:00Z')
});

// =============================================================================
// SAMPLE RELATIONSHIPS
// =============================================================================

// Schools exhibiting behaviors
MATCH (s:School {id: 'school_stanford'}), (b:BehaviorType {id: 'behavior_need_blind'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.95, sample_size: 500}]->(b);

MATCH (s:School {id: 'school_stanford'}), (b:BehaviorType {id: 'behavior_meets_full_need'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.98, sample_size: 500}]->(b);

MATCH (s:School {id: 'school_harvard'}), (b:BehaviorType {id: 'behavior_need_blind'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.95, sample_size: 600}]->(b);

MATCH (s:School {id: 'school_harvard'}), (b:BehaviorType {id: 'behavior_meets_full_need'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.98, sample_size: 600}]->(b);

MATCH (s:School {id: 'school_mit'}), (b:BehaviorType {id: 'behavior_need_blind'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.95, sample_size: 400}]->(b);

MATCH (s:School {id: 'school_usc'}), (b:BehaviorType {id: 'behavior_competes_offers'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.78, sample_size: 320}]->(b);

MATCH (s:School {id: 'school_usc'}), (b:BehaviorType {id: 'behavior_merit_focused'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.85, sample_size: 450}]->(b);

MATCH (s:School {id: 'school_umich'}), (b:BehaviorType {id: 'behavior_appeals_friendly'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.65, sample_size: 280}]->(b);

MATCH (s:School {id: 'school_asu'}), (b:BehaviorType {id: 'behavior_merit_focused'})
CREATE (s)-[:EXHIBITS_BEHAVIOR {confidence: 0.82, sample_size: 500}]->(b);

// Strategies targeting schools
MATCH (st:Strategy {id: 'strategy_competing_offer'}), (s:School {id: 'school_usc'})
CREATE (st)-[:TARGETS]->(s);

MATCH (st:Strategy {id: 'strategy_competing_offer'}), (s:School {id: 'school_umich'})
CREATE (st)-[:TARGETS]->(s);

MATCH (st:Strategy {id: 'strategy_special_circumstances'}), (s:School {id: 'school_stanford'})
CREATE (st)-[:TARGETS]->(s);

MATCH (st:Strategy {id: 'strategy_special_circumstances'}), (s:School {id: 'school_harvard'})
CREATE (st)-[:TARGETS]->(s);
