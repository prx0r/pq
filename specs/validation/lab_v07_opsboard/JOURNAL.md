# OpsBoard AgentCom v0.7 hard dogfood

## 1. OB-001 — PASS

**Tier:** `T1_SPEC`

**Hypothesis:** A longer product prompt compiles deterministically into verbatim proof obligations across local, stateful, human, authority, learning and autonomy classes.

**Expected:** At least 15 requirements and Q2/Q3/Q5/Q6/Q7/Q8 represented.

**Observed:**
```json
{
  "ok": true,
  "source_sha": "spec-source:225746ab004e5929c7a641b78f1593ae99fd5d39c0b6f8bc9cfd467ed58cb90c",
  "contract_root": "contract:98958550617656ee4f0d7ffa400b84879ff9025332c980e3c4f41fc8e9b322b6",
  "proof_root": "proofroot:a317ec6e58ddfb910b54846b3762a3320a3efcc7ef98ecf2a374d6e6a7e2668a",
  "requirements": [
    {
      "id": "R1",
      "claim": "The product MUST persist leads, jobs, settings, and audit events in SQLite and MUST survive a process restart.",
      "source_line": 5,
      "proof_class": "Q3",
      "kind": "stateful-local",
      "required_capabilities": [
        "work.minimal_plan",
        "artifact.candidate"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    },
    {
      "id": "R2",
      "claim": "CSV import MUST accept `email,name` and MUST deduplicate leads by normalized email without creating duplicates on repeated import.",
      "source_line": 6,
      "proof_class": "Q3",
      "kind": "stateful-local",
      "required_capabilities": [
        "work.minimal_plan",
        "artifact.candidate"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    },
    {
      "id": "R3",
      "claim": "The API MUST support creating a job idempotently with a client idempotency key and MUST return the same job for a repeated key.",
      "source_line": 7,
      "proof_class": "Q3",
      "kind": "stateful-local",
      "required_capabilities": [
        "work.minimal_plan",
        "artifact.candidate"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    },
    {
      "id": "R4",
      "claim": "The product MUST provide a mobile dashboard showing lead count, pending jobs, delivered jobs, spend used, and the current default view.",
      "source_line": 8,
      "proof_class": "Q6",
      "kind": "consequential",
      "required_capabilities": [
        "action.ready",
        "effect.attempted",
        "readback.independent"
      ],
      "consequential": true,
      "external": true,
      "human_boundary": "AUTHORIZATION"
    },
    {
      "id": "R5",
      "claim": "The user MUST be able to choose a low-risk default-view PREFERENCE through the 0\u20139 human-control system.",
      "source_line": 9,
      "proof_class": "Q4",
      "kind": "preference",
      "required_capabilities": [
        "human.decision"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": "PREFERENCE"
    },
    {
      "id": "R6",
      "claim": "The system MUST predict the human 0\u20139 choice before displaying each human task and MUST learn from every press after the real outcome is joined.",
      "source_line": 10,
      "proof_class": "Q8",
      "kind": "autonomy",
      "required_capabilities": [
        "human.policy.prediction",
        "human.policy.calibration"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    },
    {
      "id": "R7",
      "claim": "Increasingly familiar low-risk PREFERENCE decisions MUST become eligible for local autonomy only after calibrated verified evidence.",
      "source_line": 11,
      "proof_class": "Q8",
      "kind": "autonomy",
      "required_capabilities": [
        "human.policy.prediction",
        "human.policy.calibration"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    },
    {
      "id": "R8",
      "claim": "SECRET, IDENTITY, PHYSICAL, and consequential AUTHORIZATION tasks MUST always require real human input even if the system predicts the answer perfectly.",
      "source_line": 12,
      "proof_class": "Q5",
      "kind": "secret",
      "required_capabilities": [
        "human.decision"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": "SECRET"
    },
    {
      "id": "R9",
      "claim": "Provider credentials MUST enter only through a SECRET human task and MUST NOT be persisted in the product database, audit log, dashboard state, or ordinary trajectory logs.",
      "source_line": 13,
      "proof_class": "Q5",
      "kind": "secret",
      "required_capabilities": [
        "human.decision"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": "SECRET"
    },
    {
      "id": "R10",
      "claim": "Creating an external provider account or completing KYC MUST be represented as an IDENTITY human task and MUST NOT auto-resolve.",
      "source_line": 14,
      "proof_class": "Q5",
      "kind": "identity",
      "required_capabilities": [
        "human.decision"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": "IDENTITY"
    },
    {
      "id": "R11",
      "claim": "Dispatching a job MUST require QP-bound authority for the exact action before any external effect.",
      "source_line": 15,
      "proof_class": "Q6",
      "kind": "consequential",
      "required_capabilities": [
        "action.ready",
        "effect.attempted",
        "readback.independent"
      ],
      "consequential": true,
      "external": true,
      "human_boundary": "AUTHORIZATION"
    },
    {
      "id": "R12",
      "claim": "A campaign MUST send AT MOST 3 messages and MUST spend AT MOST 0.50 USD in total, including across restart boundaries.",
      "source_line": 16,
      "proof_class": "Q6",
      "kind": "consequential",
      "required_capabilities": [
        "action.ready",
        "effect.attempted",
        "readback.independent"
      ],
      "consequential": true,
      "external": true,
      "human_boundary": "AUTHORIZATION"
    },
    {
      "id": "R13",
      "claim": "Immediately after dispatch the local job MUST be `SENT_UNVERIFIED` and MUST NOT claim delivery from the same dispatch response.",
      "source_line": 17,
      "proof_class": "Q6",
      "kind": "consequential",
      "required_capabilities": [
        "action.ready",
        "effect.attempted",
        "readback.independent"
      ],
      "consequential": true,
      "external": true,
      "human_boundary": "AUTHORIZATION"
    },
    {
      "id": "R14",
      "claim": "Delivery MUST become `DELIVERED` only after an independent provider-side readback finds the message.",
      "source_line": 18,
      "proof_class": "Q5",
      "kind": "readback",
      "required_capabilities": [
        "probe.target",
        "readback.independent"
      ],
      "consequential": false,
      "external": true,
      "human_boundary": null
    },
    {
      "id": "R15",
      "claim": "Every local state-changing operation MUST append a SHA-256 chained audit event whose chain MUST verify after restart.",
      "source_line": 19,
      "proof_class": "Q3",
      "kind": "stateful-local",
      "required_capabilities": [
        "work.minimal_plan",
        "artifact.candidate"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    },
    {
      "id": "R16",
      "claim": "Five implementation lanes MUST use the same ContractRoot and ProofRoot; invalid lanes MUST be rejected before cost ranking.",
      "source_line": 20,
      "proof_class": "Q2",
      "kind": "local",
      "required_capabilities": [
        "work.minimal_plan",
        "artifact.candidate"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    },
    {
      "id": "R17",
      "claim": "Run 2 MUST reuse a Run-1 artifact only when the artifact has a verified proof receipt and MUST keep the same ContractRoot and ProofRoot.",
      "source_line": 21,
      "proof_class": "Q7",
      "kind": "learning",
      "required_capabilities": [
        "experiment.ranking",
        "candidate.lesson"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    },
    {
      "id": "R18",
      "claim": "FINAL ACCEPTANCE MUST produce a runnable finished product, an independent verification report, a QP receipt for the consequential action, the five-lane tournament, human-learning metrics, and a complete test journal.",
      "source_line": 22,
      "proof_class": "Q7",
      "kind": "learning",
      "required_capabilities": [
        "experiment.ranking",
        "candidate.lesson"
      ],
      "consequential": false,
      "external": false,
      "human_boundary": null
    }
  ]
}
```

**Action:** none

## 2. OB-002 — PASS

**Tier:** `T3_PROCESSOR`

**Hypothesis:** Proof/problem types select bounded processor families rather than one universal agent loop.

**Expected:** Build, H-task, autonomy, effect, readback and tournament routes all resolve.

**Observed:**
```json
{
  "ok": true,
  "plans": [
    {
      "need": "build",
      "processors": [
        "processor.plan.underengineer",
        "processor.build.code"
      ],
      "authority": false
    },
    {
      "need": "human",
      "processors": [
        "processor.escalate.hloop"
      ],
      "authority": false
    },
    {
      "need": "autonomy",
      "processors": [
        "processor.proofdesk.calibrate"
      ],
      "authority": false
    },
    {
      "need": "effect",
      "processors": [
        "processor.act.external"
      ],
      "authority": true
    },
    {
      "need": "readback",
      "processors": [
        "processor.probe.oracle"
      ],
      "authority": false
    },
    {
      "need": "tournament",
      "processors": [
        "processor.experiment.seed0"
      ],
      "authority": false
    }
  ]
}
```

**Action:** none

## 3. OB-003 — PASS

**Tier:** `T4_BUILD`

**Hypothesis:** Five isolated coding lanes can turn the same product contract into runnable implementations.

**Expected:** Five return zero with distinct artifacts.

**Observed:**
```json
{
  "ok": true,
  "runs": [
    {
      "lane_id": "lane:reuse",
      "policy": "reuse-first",
      "contract_root": "contract:98958550617656ee4f0d7ffa400b84879ff9025332c980e3c4f41fc8e9b322b6",
      "proof_root": "proofroot:a317ec6e58ddfb910b54846b3762a3320a3efcc7ef98ecf2a374d6e6a7e2668a",
      "returncode": 0,
      "elapsed_s": 1.3893,
      "changed_files": [
        "LANE.md",
        "app.js",
        "index.html",
        "lane_metrics.json",
        "opsboard.py",
        "server.py"
      ],
      "artifact_hashes": [
        [
          "LANE.md",
          "14700d7150a32f7151252391deddc1a026ab8d4456ef5b307aa717ef493280f7"
        ],
        [
          "app.js",
          "c9583ebda5a21f1bf2d49a1bd0c6b2e3aeaef8f0e695668407ef5c52ba00c185"
        ],
        [
          "index.html",
          "901e2de6bc119ba1a129ccd057f4ab05b3f4b6edc7b5bdf8ace56e86c63e2675"
        ],
        [
          "lane_metrics.json",
          "ea66a101622e7cb004263563d1b8b1a3a378d0801b0268e8c0588412542a11c8"
        ],
        [
          "opsboard.py",
          "322f15a494126f5e8c7fbccaa27f9146b3a501988dc6890e39e6392595325303"
        ],
        [
          "server.py",
          "3b02bea6128fc74d274d64f9ec89a9fef608be4e94a3271b80e2f6c4339602fa"
        ]
      ],
      "stdout_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_reuse/agent_run/stdout.log",
      "stderr_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_reuse/agent_run/stderr.log",
      "record_id": "agent-run:0b20a8ac8bff689b194d1b9f4f6746580c3708178408c2d5d0485e5cf50dfc8e"
    },
    {
      "lane_id": "lane:proof",
      "policy": "proof-first",
      "contract_root": "contract:98958550617656ee4f0d7ffa400b84879ff9025332c980e3c4f41fc8e9b322b6",
      "proof_root": "proofroot:a317ec6e58ddfb910b54846b3762a3320a3efcc7ef98ecf2a374d6e6a7e2668a",
      "returncode": 0,
      "elapsed_s": 1.3614,
      "changed_files": [
        "LANE.md",
        "app.js",
        "index.html",
        "lane_metrics.json",
        "opsboard.py",
        "server.py"
      ],
      "artifact_hashes": [
        [
          "LANE.md",
          "74b0badc813a99f0b5de1df8e0b4fc733352c394d10527cadba420f33ac1d227"
        ],
        [
          "app.js",
          "c9583ebda5a21f1bf2d49a1bd0c6b2e3aeaef8f0e695668407ef5c52ba00c185"
        ],
        [
          "index.html",
          "901e2de6bc119ba1a129ccd057f4ab05b3f4b6edc7b5bdf8ace56e86c63e2675"
        ],
        [
          "lane_metrics.json",
          "3e347e83e30839553adbfbc79facfd9cc46ab1ed92fb96ba4637955ead366ebc"
        ],
        [
          "opsboard.py",
          "322f15a494126f5e8c7fbccaa27f9146b3a501988dc6890e39e6392595325303"
        ],
        [
          "server.py",
          "3b02bea6128fc74d274d64f9ec89a9fef608be4e94a3271b80e2f6c4339602fa"
        ]
      ],
      "stdout_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_proof/agent_run/stdout.log",
      "stderr_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_proof/agent_run/stderr.log",
      "record_id": "agent-run:cf8591091bb9909c71dbf767a52c26826e77f498512fab2b644e934dad467df4"
    },
    {
      "lane_id": "lane:search",
      "policy": "search-first",
      "contract_root": "contract:98958550617656ee4f0d7ffa400b84879ff9025332c980e3c4f41fc8e9b322b6",
      "proof_root": "proofroot:a317ec6e58ddfb910b54846b3762a3320a3efcc7ef98ecf2a374d6e6a7e2668a",
      "returncode": 0,
      "elapsed_s": 1.3455,
      "changed_files": [
        "LANE.md",
        "app.js",
        "index.html",
        "lane_metrics.json",
        "opsboard.py",
        "server.py"
      ],
      "artifact_hashes": [
        [
          "LANE.md",
          "836ddf5cbcadabcbf1db3be1b4e734ddd574cac097621fc11ecf5a0f5e4f0029"
        ],
        [
          "app.js",
          "c9583ebda5a21f1bf2d49a1bd0c6b2e3aeaef8f0e695668407ef5c52ba00c185"
        ],
        [
          "index.html",
          "901e2de6bc119ba1a129ccd057f4ab05b3f4b6edc7b5bdf8ace56e86c63e2675"
        ],
        [
          "lane_metrics.json",
          "d4688e5816481dd72ebfa184c145134d7ee27d06e779c915ee09035d4b084ca6"
        ],
        [
          "opsboard.py",
          "96a32be2b0bde78b070de15acd64855aa70e8843807b094193b9efa49d218a2b"
        ],
        [
          "server.py",
          "3b02bea6128fc74d274d64f9ec89a9fef608be4e94a3271b80e2f6c4339602fa"
        ]
      ],
      "stdout_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_search/agent_run/stdout.log",
      "stderr_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_search/agent_run/stderr.log",
      "record_id": "agent-run:088b01ad04922106f6ecb951b942dcce70b0f3186bee30b54bab3ad63e801398"
    },
    {
      "lane_id": "lane:simulate",
      "policy": "simulation-first",
      "contract_root": "contract:98958550617656ee4f0d7ffa400b84879ff9025332c980e3c4f41fc8e9b322b6",
      "proof_root": "proofroot:a317ec6e58ddfb910b54846b3762a3320a3efcc7ef98ecf2a374d6e6a7e2668a",
      "returncode": 0,
      "elapsed_s": 1.3303,
      "changed_files": [
        "LANE.md",
        "app.js",
        "index.html",
        "lane_metrics.json",
        "opsboard.py",
        "server.py"
      ],
      "artifact_hashes": [
        [
          "LANE.md",
          "2a9c54fe76d100372646595e892b4add53ec5ded7236cc4e4a728006f083b7a7"
        ],
        [
          "app.js",
          "c9583ebda5a21f1bf2d49a1bd0c6b2e3aeaef8f0e695668407ef5c52ba00c185"
        ],
        [
          "index.html",
          "901e2de6bc119ba1a129ccd057f4ab05b3f4b6edc7b5bdf8ace56e86c63e2675"
        ],
        [
          "lane_metrics.json",
          "8010707f74f20f533710308ce1889cac69f88d471868fccf6cf4ea34d0b4083e"
        ],
        [
          "opsboard.py",
          "322f15a494126f5e8c7fbccaa27f9146b3a501988dc6890e39e6392595325303"
        ],
        [
          "server.py",
          "3b02bea6128fc74d274d64f9ec89a9fef608be4e94a3271b80e2f6c4339602fa"
        ]
      ],
      "stdout_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_simulate/agent_run/stdout.log",
      "stderr_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_simulate/agent_run/stderr.log",
      "record_id": "agent-run:a7eddf24592921403fda3125ed96f531a9f6be8927b74128fd5dd6d1d8d3bc3f"
    },
    {
      "lane_id": "lane:replace",
      "policy": "replacement",
      "contract_root": "contract:98958550617656ee4f0d7ffa400b84879ff9025332c980e3c4f41fc8e9b322b6",
      "proof_root": "proofroot:a317ec6e58ddfb910b54846b3762a3320a3efcc7ef98ecf2a374d6e6a7e2668a",
      "returncode": 0,
      "elapsed_s": 1.3276,
      "changed_files": [
        "LANE.md",
        "app.js",
        "index.html",
        "lane_metrics.json",
        "opsboard.py",
        "server.py"
      ],
      "artifact_hashes": [
        [
          "LANE.md",
          "009bdf30ffd9728110e6447f48f237878aa427d36d562c6f782af4ff2ed51549"
        ],
        [
          "app.js",
          "c9583ebda5a21f1bf2d49a1bd0c6b2e3aeaef8f0e695668407ef5c52ba00c185"
        ],
        [
          "index.html",
          "901e2de6bc119ba1a129ccd057f4ab05b3f4b6edc7b5bdf8ace56e86c63e2675"
        ],
        [
          "lane_metrics.json",
          "6440eea7d45dec2bfde3e069d0caf331f6953f330f51f667890c7991e49262ce"
        ],
        [
          "opsboard.py",
          "a61c8c22f05ea0a841b47a633366a6c8b10627a4b0bdc700b8fee2740cabba2a"
        ],
        [
          "server.py",
          "3b02bea6128fc74d274d64f9ec89a9fef608be4e94a3271b80e2f6c4339602fa"
        ]
      ],
      "stdout_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_replace/agent_run/stdout.log",
      "stderr_path": "/mnt/data/agentcom_control_econ_v07/agentcom_control_econ_v07/validation/results/opsboard/lanes/lane_replace/agent_run/stderr.log",
      "record_id": "agent-run:8774a2110c20166bc6245c5aad4282c03a6b497adbaf0b1594270b2333fbd862"
    }
  ]
}
```

**Action:** none

## 4. OB-004 — PASS

**Tier:** `T5_ACTUALITY`

**Hypothesis:** Independent Actuality catches secret retention and same-channel delivery even when code otherwise runs.

**Expected:** reuse/proof/simulate TRUE; search/replace FALSE.

**Observed:**
```json
{
  "ok": true,
  "rows": {
    "lane:reuse": {
      "ok": true,
      "reasons": []
    },
    "lane:proof": {
      "ok": true,
      "reasons": []
    },
    "lane:search": {
      "ok": false,
      "reasons": [
        "secret-retained"
      ]
    },
    "lane:simulate": {
      "ok": true,
      "reasons": []
    },
    "lane:replace": {
      "ok": false,
      "reasons": [
        "same-channel-truth"
      ]
    }
  }
}
```

**Action:** none

## 5. OB-005 — PASS

**Tier:** `T9_TOURNAMENT`

**Hypothesis:** Correctness dominates cost: cheap invalid builds cannot win.

**Expected:** reuse wins while cheaper search/replace are rejected.

**Observed:**
```json
{
  "ok": true,
  "winner": "lane:reuse",
  "ranked": [
    "lane:reuse",
    "lane:proof",
    "lane:simulate"
  ],
  "rejected": [
    "lane:search",
    "lane:replace"
  ]
}
```

**Action:** none

## 6. OB-006 — PASS

**Tier:** `T6_HUMAN`

**Hypothesis:** Every 0–9 press improves a local hidden policy; low-risk preference earns autonomy while secret/identity/physical/authorization never do.

**Expected:** Preference reaches AUTO_LOCAL after verified history and demotes after bad outcomes; hard boundaries stay HUMAN.

**Observed:**
```json
{
  "ok": true,
  "progression": [
    {
      "press": 1,
      "stage_before_press": "SHADOW",
      "progress": 0.1,
      "support": 0,
      "p": 0.1
    },
    {
      "press": 5,
      "stage_before_press": "SHADOW",
      "progress": 0.52,
      "support": 4,
      "p": 0.5
    },
    {
      "press": 10,
      "stage_before_press": "SUGGEST",
      "progress": 0.67,
      "support": 9,
      "p": 0.6786
    },
    {
      "press": 20,
      "stage_before_press": "SUGGEST",
      "progress": 0.97,
      "support": 19,
      "p": 0.8125
    },
    {
      "press": 40,
      "stage_before_press": "GUARDED_LOCAL",
      "progress": 1.0,
      "support": 39,
      "p": 0.8977
    },
    {
      "press": 70,
      "stage_before_press": "AUTO_LOCAL",
      "progress": 1.0,
      "support": 69,
      "p": 0.9392
    }
  ],
  "final_auto": {
    "stage": "AUTO_LOCAL",
    "progress": 0.9999999999999999,
    "predicted_key": 0,
    "probability": 0.94,
    "support": 70,
    "eligible": true,
    "reasons": [],
    "hard_human": false
  },
  "hard_boundaries": [
    {
      "class": "SECRET",
      "stage": "HUMAN",
      "hard_human": true
    },
    {
      "class": "IDENTITY",
      "stage": "HUMAN",
      "hard_human": true
    },
    {
      "class": "AUTHORIZATION",
      "stage": "HUMAN",
      "hard_human": true
    },
    {
      "class": "PHYSICAL",
      "stage": "HUMAN",
      "hard_human": true
    }
  ],
  "after_failures": {
    "stage": "GUARDED_LOCAL",
    "progress": 0.998719772403983,
    "predicted_key": 0,
    "probability": 0.8924050632911392,
    "support": 74,
    "eligible": false,
    "reasons": [
      "prediction-accuracy",
      "failure-rate"
    ],
    "hard_human": false
  },
  "metrics": {
    "n": 74,
    "accuracy": 0.9459459459459459,
    "brier": 0.1028285796230395,
    "human_seconds": 8.799999999999999,
    "validated_useful_work": 70.0,
    "autonomy_efficiency": 7.954545454545456
  },
  "macros": [
    {
      "sequence": "00",
      "keys": [
        "ACCEPT_GO",
        "ACCEPT_GO"
      ],
      "support": 69,
      "length": 2
    },
    {
      "sequence": "000",
      "keys": [
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO"
      ],
      "support": 68,
      "length": 3
    },
    {
      "sequence": "0000",
      "keys": [
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO"
      ],
      "support": 67,
      "length": 4
    },
    {
      "sequence": "00000",
      "keys": [
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO"
      ],
      "support": 66,
      "length": 5
    },
    {
      "sequence": "000000",
      "keys": [
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO"
      ],
      "support": 65,
      "length": 6
    },
    {
      "sequence": "0000000",
      "keys": [
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO"
      ],
      "support": 64,
      "length": 7
    },
    {
      "sequence": "00000000",
      "keys": [
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO",
        "ACCEPT_GO"
      ],
      "support": 63,
      "length": 8
    },
    {
      "sequence": "66",
      "keys": [
        "DENY_REPLAN",
        "DENY_REPLAN"
      ],
      "support": 3,
      "length": 2
    }
  ]
}
```

**Action:** none

## 7. OB-007 — PASS

**Tier:** `T6_HUMAN`

**Hypothesis:** Provider credentials require actual human input but raw payload stays outside logs/policy state.

**Expected:** Key 7 records behavior; authority false; only payload hash visible.

**Observed:**
```json
{
  "ok": true,
  "view": {
    "id": "provider-secret",
    "project": "opsboard",
    "class": "SECRET",
    "summary": "Provide provider credential",
    "options": [],
    "recommendation": 7,
    "cost_of_wait": 0.0,
    "risk": 0.1,
    "needed_from": "human",
    "readiness_check": "",
    "presented_at": 1789405430.2047048,
    "learning": {
      "support": 0,
      "ood": 1.0,
      "stage": "HUMAN",
      "progress": 0.1,
      "eligible": false
    }
  },
  "payload": {
    "id": "hp:89d8b6d13d2d2a06c75925f2ee2f4b5f10157fc4a8a8758a4ffe86b9e6ffbeda",
    "task_id": "provider-secret",
    "kind": "secret",
    "sha256": "d4ca827913b46754ccf3a7f9c1eb3afe375557793977ff9168480dcb1d3b376f",
    "bytes": 29,
    "created_at": 1789405430.2047524
  },
  "press": {
    "ok": true,
    "semantic": "ANSWER_CORRECT",
    "prediction_id": "pred:8e2d8ebe58122c51390ad77bd6bd84be5b7b431d262b0d4d1106cd5c1eac1c8d",
    "authority": false
  },
  "secret_exposed": false
}
```

**Action:** none

## 8. OB-008 — PASS

**Tier:** `T8_ECONOMICS`

**Hypothesis:** Model choice is learned per proof class and expected verified-completion cost.

**Expected:** Cheap model wins Q2; reliable model wins Q6.

**Observed:**
```json
{
  "ok": true,
  "q2": "cheap",
  "q6": "frontier",
  "plan": {
    "route_id": "frontier",
    "model": "frontier",
    "provider": "premium",
    "expected_cost_verified": 0.07796323529411765,
    "p_success": 0.9411764705882353,
    "exploit_cap": 0.3818181818181819,
    "explore_cap": 0.09545454545454547,
    "proof_class": "Q6",
    "task_family": "opsboard-build",
    "requires_qp_spend_grant": true,
    "provenance": [
      "fixture:market"
    ]
  }
}
```

**Action:** none

## 9. OB-009 — PASS

**Tier:** `T7_AUTHORITY`

**Hypothesis:** The finished product cannot perform its consequential action without a signed call-scoped QP grant, and delivery requires independent readback.

**Expected:** SENT_UNVERIFIED → independent readback → DELIVERED → QP replay PASS.

**Observed:**
```json
{
  "ok": true,
  "grant": {
    "ok": true,
    "reason": "grant authorizes action"
  },
  "receipt_id": "receipt:d6c16522b353f874",
  "before": "SENT_UNVERIFIED",
  "after": "DELIVERED",
  "settled": {
    "ok": true,
    "reason": "all gates replay identically"
  }
}
```

**Action:** none
