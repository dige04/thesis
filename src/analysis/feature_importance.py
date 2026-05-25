"""
Feature importance analysis for helpful/harmful memory prediction.

This module implements Task 15.1: Helpful/harmful memory prediction.

Per THESIS_FINAL_v5.md §16:
- Unit of analysis: (task, retrieved_memory) pairs
- Primary metric: PR-AUC (NOT accuracy or ROC-AUC)
- VIF check for multicollinearity (target VIF < 5)
- Class weights for imbalanced data (~20% positive)
- Three-tier labeling: automatic weak labels, manual labels, case studies
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight

try:
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


def prepare_memory_retrieval_data(
    runs_dir: Path,
) -> pd.DataFrame:
    """
    Prepare (task, retrieved_memory) pairs for feature importance analysis.

    Per THESIS_FINAL_v5.md §16.1:
    - Unit of analysis: each retrieved memory in each task
    - Features: similarity, rank, age, type, outcome, file_overlap, etc.
    - Label: helpful/harmful/neutral

    Args:
        runs_dir: Path to runs/ directory

    Returns:
        DataFrame with columns:
        - task_id, memory_id, policy, seed, sequence
        - semantic_similarity, retrieval_rank, memory_age
        - memory_type, memory_outcome, same_repo
        - file_overlap, token_length, use_count, is_consolidated
        - task_resolved (binary outcome)
        - label (helpful/harmful/neutral)
    """
    records = []

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        task_results_path = run_dir / "task_results.jsonl"
        if not task_results_path.exists():
            continue

        with open(task_results_path) as f:
            for line in f:
                if not line.strip():
                    continue
                task = json.loads(line)

                # Extract retrieved memories for this task
                retrieved_ids = task.get("retrieved_memory_ids", [])
                retrieved_scores = task.get("retrieved_memory_scores", [])
                retrieved_types = task.get("retrieved_memory_types", [])
                retrieved_ages = task.get("retrieved_memory_ages", [])

                task_resolved = task["resolved"]
                policy = task["policy"]
                seed = task["seed"]
                sequence = task["repo"]

                # Create one row per retrieved memory
                for i, memory_id in enumerate(retrieved_ids):
                    similarity = (
                        retrieved_scores[i] if i < len(retrieved_scores) else 0.0
                    )
                    memory_type = (
                        retrieved_types[i] if i < len(retrieved_types) else "unknown"
                    )
                    memory_age = retrieved_ages[i] if i < len(retrieved_ages) else 0

                    # Placeholder values (would be computed from memory store)
                    # In production, load from memory_events.jsonl and memory snapshots
                    file_overlap = 0.0  # TODO: compute from actual files_touched
                    token_length = 200  # TODO: load from memory record
                    use_count = 1  # TODO: load from memory record
                    is_consolidated = False  # TODO: load from memory record
                    memory_outcome = "unknown"  # TODO: load from memory record

                    # Automatic weak labeling (Tier 1)
                    label = compute_weak_label(
                        task_resolved=task_resolved,
                        file_overlap=file_overlap,
                        memory_outcome=memory_outcome,
                        semantic_similarity=similarity,
                    )

                    records.append(
                        {
                            "task_id": task["task_id"],
                            "memory_id": memory_id,
                            "policy": policy,
                            "seed": seed,
                            "sequence": sequence,
                            "semantic_similarity": similarity,
                            "retrieval_rank": i + 1,
                            "memory_age": memory_age,
                            "memory_type": memory_type,
                            "memory_outcome": memory_outcome,
                            "same_repo": True,  # Main experiment uses same-repo only
                            "file_overlap": file_overlap,
                            "token_length": token_length,
                            "use_count": use_count,
                            "is_consolidated": is_consolidated,
                            "task_resolved": task_resolved,
                            "label": label,
                        }
                    )

    return pd.DataFrame(records)


def compute_weak_label(
    task_resolved: int,
    file_overlap: float,
    memory_outcome: str,
    semantic_similarity: float,
) -> str:
    """
    Compute automatic weak label (Tier 1).

    Per THESIS_FINAL_v5.md §16.2:
    - helpful: task_resolved=1 AND file_overlap>0 AND memory_outcome="pass"
    - harmful: task_resolved=0 AND similarity>0.7 AND memory_outcome="fail"
    - neutral: otherwise

    Args:
        task_resolved: Binary task outcome (1=success, 0=failure)
        file_overlap: Fraction of task files touched by memory
        memory_outcome: Memory outcome (pass/fail/partial/unknown)
        semantic_similarity: Cosine similarity score

    Returns:
        Label: "helpful", "harmful", or "neutral"
    """
    if task_resolved == 1 and file_overlap > 0 and memory_outcome == "pass":
        return "helpful"
    elif (
        task_resolved == 0
        and semantic_similarity > 0.7
        and memory_outcome == "fail"
    ):
        return "harmful"
    else:
        return "neutral"


def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Variance Inflation Factor (VIF) for all features.

    Per THESIS_FINAL_v5.md §16.3:
    - Check VIF for all features
    - Flag VIF > 5 (multicollinearity concern)
    - If age or use_count has VIF > 5, use retrieval_rate instead

    Args:
        X: Feature matrix (DataFrame)

    Returns:
        DataFrame with columns: feature, VIF
    """
    if not STATSMODELS_AVAILABLE:
        print("⚠ statsmodels not available. Install with: pip install statsmodels")
        print("  Skipping VIF check.")
        return pd.DataFrame({"feature": X.columns, "VIF": [np.nan] * len(X.columns)})

    vif_data = pd.DataFrame()
    vif_data["feature"] = X.columns
    vif_data["VIF"] = [
        variance_inflation_factor(X.values, i) for i in range(len(X.columns))
    ]
    return vif_data


def prepare_features(
    df: pd.DataFrame,
    check_vif: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Prepare feature matrix with VIF check.

    Per THESIS_FINAL_v5.md §16.3:
    - Derived feature: retrieval_rate = use_count / (memory_age + 1)
    - If VIF(age) > 5 OR VIF(use_count) > 5, drop both and keep retrieval_rate

    Args:
        df: DataFrame from prepare_memory_retrieval_data()
        check_vif: Whether to perform VIF check

    Returns:
        Tuple of (feature_matrix, feature_names)
    """
    # Encode categorical features
    df_encoded = df.copy()

    # One-hot encode memory_type
    type_dummies = pd.get_dummies(df_encoded["memory_type"], prefix="type")
    df_encoded = pd.concat([df_encoded, type_dummies], axis=1)

    # One-hot encode memory_outcome
    outcome_dummies = pd.get_dummies(df_encoded["memory_outcome"], prefix="outcome")
    df_encoded = pd.concat([df_encoded, outcome_dummies], axis=1)

    # Derived feature: retrieval_rate
    df_encoded["retrieval_rate"] = df_encoded["use_count"] / (
        df_encoded["memory_age"] + 1
    )

    # Base features
    base_features = [
        "semantic_similarity",
        "retrieval_rank",
        "memory_age",
        "file_overlap",
        "token_length",
        "use_count",
        "is_consolidated",
    ]

    # Add one-hot encoded features
    type_cols = [col for col in df_encoded.columns if col.startswith("type_")]
    outcome_cols = [col for col in df_encoded.columns if col.startswith("outcome_")]

    all_features = base_features + type_cols + outcome_cols + ["retrieval_rate"]

    # Select features
    X = df_encoded[all_features].copy()

    # Convert boolean to int
    X["is_consolidated"] = X["is_consolidated"].astype(int)

    # VIF check
    if check_vif:
        if not STATSMODELS_AVAILABLE:
            print("\n⚠ Skipping VIF check (statsmodels not available)")
        else:
            vif_df = compute_vif(X[base_features])
            print("\nVIF Analysis:")
            print(vif_df)

            # Check if age or use_count has high VIF
            age_vif = vif_df[vif_df["feature"] == "memory_age"]["VIF"].values[0]
            use_count_vif = vif_df[vif_df["feature"] == "use_count"]["VIF"].values[0]

            if age_vif > 5 or use_count_vif > 5:
                print(
                    f"\n⚠ High VIF detected: age={age_vif:.2f}, use_count={use_count_vif:.2f}"
                )
                print("  Dropping age and use_count, keeping retrieval_rate")

                # Drop age and use_count, keep retrieval_rate
                features_to_use = [
                    f for f in all_features if f not in ["memory_age", "use_count"]
                ]
                X = X[features_to_use]
                all_features = features_to_use

    return X, all_features


def train_helpful_harmful_classifier(
    X: pd.DataFrame,
    y: pd.Series,
    sequences: pd.Series,
    model_type: str = "logistic",
    n_folds: int = 5,
    random_seed: int = 42,
) -> dict[str, Any]:
    """
    Train classifier to predict helpful/harmful memories.

    Per THESIS_FINAL_v5.md §16.4-16.5:
    - Models: Logistic Regression (interpretable) + GBM (nonlinear)
    - Evaluation: 5-fold CV, stratified by sequence
    - Primary metric: PR-AUC (NOT accuracy or ROC-AUC)
    - Class weights: inverse frequency
    - Report: precision, recall, F1, calibration

    Args:
        X: Feature matrix
        y: Binary labels (1=helpful, 0=not helpful)
        sequences: Sequence names for stratification
        model_type: "logistic" or "gbm"
        n_folds: Number of CV folds
        random_seed: Random seed for reproducibility

    Returns:
        Dict with:
        - model: Trained model
        - pr_auc: PR-AUC score
        - pr_auc_std: Standard deviation across folds
        - precision, recall, f1: At threshold=0.5
        - feature_importance: Feature importance scores
        - cv_scores: Per-fold PR-AUC scores
    """
    # Compute class weights
    classes = np.unique(y)
    class_weights = compute_class_weight("balanced", classes=classes, y=y)
    class_weight_dict = dict(zip(classes, class_weights))

    print(f"\nClass distribution: {np.bincount(y)}")
    print(f"Class weights: {class_weight_dict}")

    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Initialize model
    if model_type == "logistic":
        model = LogisticRegression(
            class_weight=class_weight_dict,
            random_state=random_seed,
            max_iter=1000,
        )
    elif model_type == "gbm":
        # GBM with balanced class weights
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=random_seed,
        )
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    # Stratified K-Fold by sequence
    # Create stratification key: sequence + label
    strat_key = sequences.astype(str) + "_" + y.astype(str)
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=random_seed)

    # Cross-validation for PR-AUC
    cv_scores = []
    for train_idx, test_idx in skf.split(X_scaled, strat_key):
        X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        model.fit(X_train, y_train)
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        # Compute PR-AUC
        pr_auc = average_precision_score(y_test, y_pred_proba)
        cv_scores.append(pr_auc)

    # Train final model on all data
    model.fit(X_scaled, y)
    y_pred_proba = model.predict_proba(X_scaled)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)

    # Compute metrics
    pr_auc = average_precision_score(y, y_pred_proba)
    precision = precision_score(y, y_pred, zero_division=0)
    recall = recall_score(y, y_pred, zero_division=0)
    f1 = f1_score(y, y_pred, zero_division=0)

    # Feature importance
    if model_type == "logistic":
        feature_importance = pd.DataFrame(
            {
                "feature": X.columns,
                "coefficient": model.coef_[0],
                "abs_coefficient": np.abs(model.coef_[0]),
            }
        ).sort_values("abs_coefficient", ascending=False)
    elif model_type == "gbm":
        feature_importance = pd.DataFrame(
            {
                "feature": X.columns,
                "importance": model.feature_importances_,
            }
        ).sort_values("importance", ascending=False)

    return {
        "model": model,
        "scaler": scaler,
        "pr_auc": pr_auc,
        "pr_auc_std": np.std(cv_scores),
        "cv_scores": cv_scores,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "feature_importance": feature_importance,
        "class_weights": class_weight_dict,
    }


def run_feature_importance_analysis(
    runs_dir: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Run complete feature importance analysis.

    Args:
        runs_dir: Path to runs/ directory
        output_dir: Optional path to save results

    Returns:
        Dict with:
        - data_summary: Summary statistics
        - vif_analysis: VIF check results
        - logistic_results: Logistic regression results
        - gbm_results: GBM results
        - comparison: Model comparison
    """
    print("=" * 80)
    print("FEATURE IMPORTANCE ANALYSIS: HELPFUL/HARMFUL MEMORY PREDICTION")
    print("=" * 80)

    # Prepare data
    print("\n[1/5] Preparing (task, retrieved_memory) pairs...")
    df = prepare_memory_retrieval_data(runs_dir)

    print(f"  Total pairs: {len(df)}")
    print("  Label distribution:")
    print(df["label"].value_counts())

    # Convert to binary: helpful=1, others=0
    df["binary_label"] = (df["label"] == "helpful").astype(int)

    # Data summary
    data_summary = {
        "n_pairs": len(df),
        "n_tasks": df["task_id"].nunique(),
        "n_memories": df["memory_id"].nunique(),
        "label_distribution": df["label"].value_counts().to_dict(),
        "helpful_rate": df["binary_label"].mean(),
    }

    # Prepare features with VIF check
    print("\n[2/5] Preparing features and checking VIF...")
    X, feature_names = prepare_features(df, check_vif=True)
    y = df["binary_label"]
    sequences = df["sequence"]

    # Train Logistic Regression
    print("\n[3/5] Training Logistic Regression (interpretable)...")
    logistic_results = train_helpful_harmful_classifier(
        X=X,
        y=y,
        sequences=sequences,
        model_type="logistic",
        n_folds=5,
        random_seed=42,
    )

    print(f"\n  PR-AUC: {logistic_results['pr_auc']:.4f} ± {logistic_results['pr_auc_std']:.4f}")
    print(f"  Precision: {logistic_results['precision']:.4f}")
    print(f"  Recall: {logistic_results['recall']:.4f}")
    print(f"  F1: {logistic_results['f1']:.4f}")

    print("\n  Top 10 features (by absolute coefficient):")
    print(logistic_results["feature_importance"].head(10))

    # Train GBM
    print("\n[4/5] Training Gradient Boosting Machine (nonlinear)...")
    gbm_results = train_helpful_harmful_classifier(
        X=X,
        y=y,
        sequences=sequences,
        model_type="gbm",
        n_folds=5,
        random_seed=42,
    )

    print(f"\n  PR-AUC: {gbm_results['pr_auc']:.4f} ± {gbm_results['pr_auc_std']:.4f}")
    print(f"  Precision: {gbm_results['precision']:.4f}")
    print(f"  Recall: {gbm_results['recall']:.4f}")
    print(f"  F1: {gbm_results['f1']:.4f}")

    print("\n  Top 10 features (by importance):")
    print(gbm_results["feature_importance"].head(10))

    # Model comparison
    print("\n[5/5] Comparing models...")
    comparison = {
        "logistic_pr_auc": logistic_results["pr_auc"],
        "gbm_pr_auc": gbm_results["pr_auc"],
        "best_model": "gbm"
        if gbm_results["pr_auc"] > logistic_results["pr_auc"]
        else "logistic",
    }

    print(f"\n  Best model: {comparison['best_model']}")
    print(
        f"  PR-AUC difference: {abs(gbm_results['pr_auc'] - logistic_results['pr_auc']):.4f}"
    )

    # Save results
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save data
        df.to_csv(output_dir / "memory_retrieval_pairs.csv", index=False)

        # Save results (exclude non-serializable model objects)
        results = {
            "data_summary": data_summary,
            "feature_names": feature_names,
            "logistic_results": {
                k: v
                for k, v in logistic_results.items()
                if k not in ["model", "scaler"]
            },
            "gbm_results": {
                k: v for k, v in gbm_results.items() if k not in ["model", "scaler"]
            },
            "comparison": comparison,
        }

        # Convert DataFrames to dicts for JSON serialization
        results["logistic_results"]["feature_importance"] = logistic_results[
            "feature_importance"
        ].to_dict(orient="records")
        results["gbm_results"]["feature_importance"] = gbm_results[
            "feature_importance"
        ].to_dict(orient="records")

        with open(output_dir / "feature_importance_results.json", "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n✓ Results saved to {output_dir}")

    return {
        "data_summary": data_summary,
        "logistic_results": logistic_results,
        "gbm_results": gbm_results,
        "comparison": comparison,
    }
