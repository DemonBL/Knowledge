// ЛР14 · відкат міграції якості
MATCH (c:Claim) REMOVE c.status;
MATCH (n:Narrative) REMOVE n.claimCount, n.publicationCount;
MATCH (v:Verdict) REMOVE v.complianceStatus;
MATCH (v:Verdict) REMOVE v.firstSeenAt, v.temporalFlag;
MATCH (r:Rule) REMOVE r.alias, r.altCondition;
