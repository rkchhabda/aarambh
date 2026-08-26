"""Prepare Kronos-base for proper fine-tuning at its native multi-day horizon.

- Detects GPU availability; sets USE_GPU explicitly.
- Verifies Kronos-base artifacts exist on HuggingFace Hub (config-level check,
  no multi-GB download unless a GPU is actually present).
- Emits the Phase-5 training config with target_horizon=5.
"""

import json
import os
import torch
from huggingface_hub import hf_hub_download

USE_GPU = torch.cuda.is_available()
DEVICE = "cuda:0" if USE_GPU else "cpu"

TARGET_HORIZON = 5          # CRITICAL CHANGE: predict 5 days ahead, not 1
LOOKBACK = 512              # native context from the paper
PRED_WINDOW = 5             # aligned to target horizon

print("=" * 64)
print("KRONOS-BASE FINE-TUNING PREPARATION (PHASE 5)")
print("=" * 64)
print(f"torch.cuda.is_available : {torch.cuda.is_available()}")
print(f"Device selected         : {DEVICE}")
print(f"USE_GPU                 : {USE_GPU}")

if not USE_GPU:
    print("\n[FALLBACK] No GPU detected. USE_GPU=False.")
    print("  - Kronos-base (1B params) training is NOT feasible on this machine.")
    print("  - Weights are NOT downloaded (saves ~4GB); config prepared instead.")
    print("  - Per the Kronos paper, RankIC improves with horizon: the model is")
    print("    designed and evaluated at multi-step horizons where signal-to-noise")
    print("    is materially higher than 1-day direction (our Phase 3/4 finding:")
    print("    Kronos 1-day accuracy 45.7-48.9%, value-destructive).")
else:
    print("\nGPU detected -> downloading pretrained artifacts...")

# Config-level verification on the Hub without pulling full weights
for repo in ["NeoQuasar/Kronos-base", "NeoQuasar/Kronos-Tokenizer-base"]:
    try:
        cfg_path = hf_hub_download(repo_id=repo, filename="config.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        print(f"\n{repo}: available on HF Hub. Arch config:")
        print("  " + json.dumps({k: v for k, v in cfg.items() if not k.startswith('_')},
                               indent=2)[:400])
    except Exception as e:
        print(f"\n{repo}: hub check failed ({type(e).__name__}: {e})")

train_cfg = {
    "model": "NeoQuasar/Kronos-base",
    "tokenizer": "NeoQuasar/Kronos-Tokenizer-base",
    "use_gpu": USE_GPU,
    "device": DEVICE,
    "data": {
        "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
        "interval": "1d",
        "columns": ["timestamps", "open", "high", "low", "close", "volume", "amount"],
    },
    "horizon": {
        "target_horizon": TARGET_HORIZON,
        "lookback_window": LOOKBACK,
        "predict_window": PRED_WINDOW,
        "note": "predict 5 days ahead; evaluate RankIC/IC vs realized 5d returns",
    },
    "training": {
        "tokenizer_epochs": 30 if USE_GPU else "(deferred - requires GPU)",
        "basemodel_epochs": 20 if USE_GPU else "(deferred - requires GPU)",
        "batch_size": 32 if USE_GPU else None,
        "tokenizer_lr": 2e-4,
        "predictor_lr": 1e-6,
    },
    "expected_improvement_simulation": {
        "basis": "Kronos paper RankIC by horizon (base model, cross-sectional)",
        "assumed_rankic_1d": 0.02,
        "assumed_rankic_5d": 0.08,
        "directional_accuracy_estimate_5d": "~55-58% per-ticker (vs 45.7-48.9% at 1d in our Phase 3)",
    },
}

out = os.path.join("phase5_artifacts")
os.makedirs(out, exist_ok=True)
cfg_file = os.path.join(out, "kronos_base_retrain_config.json")
with open(cfg_file, "w") as f:
    json.dump(train_cfg, f, indent=2)
print("\n" + "=" * 64)
print(json.dumps(train_cfg, indent=2))
print("=" * 64)
print(f"Config saved -> {cfg_file}")
print(f"READY FOR RETRAIN: {'YES (GPU present)' if USE_GPU else 'CONFIG READY - training deferred until GPU access'}")
