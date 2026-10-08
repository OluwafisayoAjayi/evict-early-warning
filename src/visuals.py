"""Pure display logic used by the Streamlit dashboard (no made-up research outputs)."""
import numpy as np
import pandas as pd


def prepare_map_categories(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Classify observed-coverage counties for *descriptive*, unvalidated map display.

    The 75th percentile is calculated over ALL tracked counties in the selected
    forecast horizon, not within a state filter, for consistent comparisons.
    These are not probabilities of individual household eviction.
    """
    d = forecasts.copy()
    d['fips'] = d.fips.astype(str).str.zfill(5)
    d['predicted_rate_per_1000_renter_households'] = pd.to_numeric(
        d['predicted_rate_per_1000_renter_households'], errors='coerce')
    d['predicted_filings'] = pd.to_numeric(d['predicted_filings'], errors='coerce')
    d['roll_12'] = pd.to_numeric(d['roll_12'], errors='coerce')
    rate = d.predicted_rate_per_1000_renter_households
    valid = rate.replace([np.inf, -np.inf], np.nan).dropna()
    if valid.empty:
        raise ValueError('No valid filing rates for the requested forecast horizon')
    p75 = float(valid.quantile(.75))
    # Prefer transparent categories with distinguishable meanings.
    d['map_category'] = 'Other tracked counties'
    d.loc[rate.ge(p75), 'map_category'] = 'Higher forecast filing rate (top 25%)'
    # An emerging rise is conceptually different from a persistently high rate.
    alert = (d.predicted_filings.ge(5) & d.roll_12.gt(0) &
             d.predicted_filings.ge(1.25 * d.roll_12))
    d.loc[alert, 'map_category'] = 'Emerging increase (experimental alert)'
    d['change_vs_12m_pct'] = np.where(
        d.roll_12.gt(0), 100 * (d.predicted_filings / d.roll_12 - 1), np.nan)
    d['map_p75_threshold'] = p75
    return d


def retrospective_metrics(backtests: pd.DataFrame) -> pd.DataFrame:
    """Recalculate errors for exactly the county-months currently filtered."""
    rows = []
    for column, label in [
        ('baseline_last', 'Last observed month'),
        ('baseline_seasonal', 'Same month previous year'),
        ('model_history', 'Past filings + seasonality'),
        ('model_history_acs', 'Past filings + ACS')]:
        sample = backtests[['filings', column]].apply(pd.to_numeric, errors='coerce').dropna()
        if sample.empty:
            continue
        error = (sample.filings - sample[column]).abs()
        rows.append({
            'Model': label, 'MAE (filings)': round(float(error.mean()), 2),
            'WAPE (%)': round(float(100 * error.sum() / sample.filings.sum()), 2)
            if sample.filings.sum() > 0 else np.nan,
            'County-months tested': len(sample)})
    return pd.DataFrame(rows)


def alert_quality(backtests: pd.DataFrame) -> dict:
    """Evaluate a fixed, experimental rising-filings rule on held-out rows."""
    b = backtests.dropna(subset=['filings', 'roll_12', 'model_history_acs']).copy()
    if b.empty:
        return {}
    actual = (b.filings.ge(5) & b.roll_12.gt(0) & b.filings.ge(1.25 * b.roll_12))
    predicted = (b.model_history_acs.ge(5) & b.roll_12.gt(0) &
                 b.model_history_acs.ge(1.25 * b.roll_12))
    tp = int((actual & predicted).sum())
    fp = int((~actual & predicted).sum())
    fn = int((actual & ~predicted).sum())
    return {'True alerts': tp, 'False alerts': fp, 'Missed rises': fn,
            'Precision': round(tp/(tp+fp), 3) if tp+fp else None,
            'Recall': round(tp/(tp+fn), 3) if tp+fn else None}
