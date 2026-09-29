# Standing Rule: Zero Exposure of Passwords and Secrets

**Rule Scope:** GaurviDEEP Research, Pre-Registration Holdouts, and Production Operations.

1. **Owner-Held Secrets Invariant:**
   - Any password, encryption key, or secret associated with holdout datasets, sealed archives, private certificates, or production environments MUST be generated exclusively by the human owner (e.g., via a local password manager or owner-controlled terminal).
   - No agent, script, subagent, or automated process may generate, infer, or store these passwords.

2. **Zero Disclosure in Outputs:**
   - Secrets must NEVER appear in any chat response, report, log file, commit message, code comment, or document.
   - Any report or documentation task involving secrets must exclusively output the standing confirmation placeholder:
     `"password generated and stored securely by owner — not printed"`
