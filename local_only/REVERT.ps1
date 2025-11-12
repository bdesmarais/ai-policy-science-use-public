# REVERT.ps1 - Undo press_releases_proj archive reorganization.
# Run from repository root. Review pending changes before executing.

$coreReverts = @(
    @{ Source = "scripts/core/analyze_press_releases_v3.py"; Target = "analyze_press_releases_v3.py" },
    @{ Source = "scripts/core/llm_claims.py";               Target = "llm_claims.py" },
    @{ Source = "scripts/core/gpt_references.py";           Target = "gpt_references.py" },
    @{ Source = "scripts/core/summarize_structured_references.py"; Target = "summarize_structured_references.py" }
)
$pilotReverts = @(
    @{ Source = "scripts/pilot/prepare_pilot_annotations.py"; Target = "prepare_pilot_annotations.py" },
    @{ Source = "scripts/pilot/triage_false_positives.py";    Target = "triage_false_positives.py" },
    @{ Source = "scripts/pilot/evaluate_ai_statements.py";    Target = "evaluate_ai_statements.py" },
    @{ Source = "scripts/pilot/analyze_annotations.py";       Target = "analyze_annotations.py" },
    @{ Source = "scripts/pilot/assist_zack_prefill.py";       Target = "assist_zack_prefill.py" },
    @{ Source = "scripts/pilot/sample_transport_docs.py";     Target = "sample_transport_docs.py" },
    @{ Source = "scripts/pilot/train_doc_classifier.py";      Target = "train_doc_classifier.py" }
)
$legacyReverts = @(
    @{ Source = "archive/analyze_press_releases_v2.py";     Target = "analyze_press_releases_v2.py" },
    @{ Source = "archive/build_claim_lists.py";             Target = "build_claim_lists.py" },
    @{ Source = "archive/structured_references.py";         Target = "structured_references.py" },
    @{ Source = "archive/summarize_ai_reference_counts.py"; Target = "summarize_ai_reference_counts.py" }
)

foreach ($item in $coreReverts + $pilotReverts + $legacyReverts) {
    if (Test-Path $item.Source -and -not (Test-Path $item.Target)) {
        Move-Item -LiteralPath $item.Source -Destination $item.Target
    }
}

if (Test-Path "archive/outputs_snapshot_20251112") {
    Write-Host "Snapshot directory 'archive\outputs_snapshot_20251112' remains in place; remove manually if desired." -ForegroundColor Yellow
}
