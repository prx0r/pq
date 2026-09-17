SCARCITY_WEIGHTS = {
    "external_state":1.45,
    "authority":1.40,
    "trajectories":1.45,
    "network":1.10,
    "physical":1.30,
    "trust":1.15,
    "longitudinal_state":1.20,
    "ai_complementarity":1.35,
    "verifiability":1.00,
    "externality":1.45,
}

FRAGILITY_WEIGHTS = {
    "wrapper_risk":1.25,
    "public_replicability":1.15,
    "platform_capture":1.10,
    "synthetic_substitutability":1.30,
    "internalization_risk":1.45,
    "human_distribution_burden":0.55,
}

FEATURE_WEIGHTS_POS = {
    "external_state":0.20,
    "authority":0.18,
    "trajectories":0.18,
    "ai_complementarity":0.12,
    "scarcity":0.10,
    "trust":0.08,
    "verifiability":0.08,
    "necessity":0.06,
}
FEATURE_WEIGHTS_NEG = {
    "lab_attack":0.18,
    "public_replicability":0.12,
    "maintenance":0.10,
}

def clamp(x, lo=0.0, hi=5.0):
    return max(lo, min(hi, float(x)))

def weighted_norm(d, weights):
    denom = sum(weights.values()) * 5.0
    if not denom:
        return 0.0
    return sum(weights[k] * clamp(d.get(k, 0)) for k in weights) / denom

def project_score(project):
    s = weighted_norm(project.get("scarcity",{}), SCARCITY_WEIGHTS)
    q = weighted_norm(project.get("fragility",{}), FRAGILITY_WEIGHTS)

    own = project.get("ownership",{})
    ownership = sum(clamp(own.get(k,0)) for k in ["state","authority","trajectories","network","supply"]) / 25.0

    moat = max(0.0, min(1.0, s - 0.55*q))
    strategic = moat * (0.45 + 0.55*ownership)

    if strategic >= 0.62:
        action = "OWN/ACCELERATE"
    elif strategic >= 0.45:
        action = "BUILD SELECTIVELY"
    elif strategic >= 0.30:
        action = "VALIDATE / OWN ONLY SCARCE LAYERS"
    else:
        action = "REUSE / WATCH / DROP"

    return {
        "scarcity_strength": round(s*100,1),
        "fragility": round(q*100,1),
        "ownership": round(ownership*100,1),
        "moat": round(moat*100,1),
        "strategic_value": round(strategic*100,1),
        "action": action
    }

def feature_score(feature):
    s = feature.get("scores",{})
    pos = sum(w * clamp(s.get(k,0))/5.0 for k,w in FEATURE_WEIGHTS_POS.items())
    neg = sum(w * clamp(s.get(k,0))/5.0 for k,w in FEATURE_WEIGHTS_NEG.items())
    raw = max(0.0, min(1.0, pos-neg))
    score = raw*100

    ext = clamp(s.get("external_state",0))
    auth = clamp(s.get("authority",0))
    traj = clamp(s.get("trajectories",0))
    lab = clamp(s.get("lab_attack",0))
    rep = clamp(s.get("public_replicability",0))
    nec = clamp(s.get("necessity",0))
    scarce = clamp(s.get("scarcity",0))

    if max(ext, auth, traj) >= 4 and lab <= 2:
        action = "OWN"
    elif score >= 48 and nec >= 4 and rep <= 3:
        action = "BUILD"
    elif lab >= 4 and rep >= 4:
        action = "REUSE"
    elif score >= 30 and scarce >= 3:
        action = "VALIDATE"
    elif nec <= 2 and score < 25:
        action = "DROP"
    else:
        action = "WATCH"

    return {"score":round(score,1),"action":action}
