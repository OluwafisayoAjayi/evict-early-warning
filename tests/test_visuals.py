import numpy as np
import pandas as pd
from src.visuals import prepare_map_categories, retrospective_metrics, alert_quality


def fixture():
    return pd.DataFrame({'fips':['09001','09003','09005','09007'],
        'predicted_filings':[40,35,10,2], 'roll_12':[10,50,10,3],
        'predicted_rate_per_1000_renter_households':[18.,14.,7.,2.]})


def test_map_categories_alert_and_rate_are_distinct():
    out=prepare_map_categories(fixture()).set_index('fips')
    assert out.loc['09001','map_category']=='Emerging increase (experimental alert)'
    assert out.loc['09003','map_category']=='Other tracked counties'
    assert out.loc['09005','map_category']=='Other tracked counties'
    assert out.loc['09007','map_category']=='Other tracked counties'
    assert out.loc['09001','change_vs_12m_pct']==300.0


def test_top_quartile_without_alert_is_red():
    f=fixture(); f.loc[0,'roll_12']=60
    out=prepare_map_categories(f).set_index('fips')
    assert out.loc['09001','map_category']=='Higher forecast filing rate (top 25%)'


def test_missing_rate_is_not_treated_as_safe():
    f=fixture();f['predicted_rate_per_1000_renter_households']=np.nan
    import pytest
    with pytest.raises(ValueError):prepare_map_categories(f)


def test_retrospective_error_metrics_observed_and_model():
    b=pd.DataFrame({'filings':[8,12], 'baseline_last':[6,10],
        'baseline_seasonal':[10,10], 'model_history':[8,12], 'model_history_acs':[9,11]})
    m=retrospective_metrics(b).set_index('Model')
    assert m.loc['Past filings + seasonality','MAE (filings)']==0
    assert m.loc['Past filings + ACS','WAPE (%)']==10
    assert m.loc['Last observed month','County-months tested']==2


def test_alert_quality_historical_truth_and_false_positive():
    b=pd.DataFrame({'filings':[16,5,10],'roll_12':[10,10,10],
                   'model_history_acs':[20,20,10]})
    a=alert_quality(b)
    assert a['True alerts']==1
    assert a['False alerts']==1
    assert a['Missed rises']==0
    assert a['Precision']==.5
