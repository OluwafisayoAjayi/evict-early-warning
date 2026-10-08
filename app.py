"""Evict-AI: live-data-only US county forecasting research dashboard.

All measurements come from explicit exported outputs of the reproducible
pipeline. No demo estimates, synthetic counties, or invented accuracies appear.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from src.config import OUT
from src.prepare_panel import STATES
from src.visuals import prepare_map_categories, retrospective_metrics, alert_quality

st.set_page_config(page_title='Evict-AI | Eviction Early Warning', page_icon='🏘️', layout='wide')
st.markdown("""<style>
.block-container {padding-top:1.4rem;padding-bottom:3rem;max-width:1420px;}
[data-testid="stMetric"] {border:1px solid #e1e7eb;border-radius:12px;padding:11px 15px;}
[data-testid="stMetricLabel"] {font-size:.84rem;}
[data-testid="stSidebar"] {border-right:1px solid #e8ecef;}
</style>""", unsafe_allow_html=True)

NAME_OF_STATE = {v: n.title() for n, v in STATES.items()}
NAME_OF_STATE['11'] = 'District of Columbia'
NAME_OF_STATE['72'] = 'Puerto Rico'
SHAPES_URL = 'https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json'
MAP_COLORS = {
    'Emerging increase (experimental alert)': '#E66A3C',
    'Higher forecast filing rate (top 25%)': '#C13549',
    'Other tracked counties': '#31847C',
}

@st.cache_data(ttl=86400, show_spinner=False)
def load_shapes():
    """Public Plotly county geometry, independent of observed court-data source."""
    response = requests.get(SHAPES_URL, timeout=25, headers={'User-Agent': 'Evict-AI-Research/0.3'})
    response.raise_for_status()
    if len(response.content) > 8_000_000:
        raise ValueError('GeoJSON file exceeds expected size')
    data = response.json()
    if data.get('type') != 'FeatureCollection' or len(data.get('features', [])) < 2500:
        raise ValueError('Unexpected county boundary data')
    return data

@st.cache_data(ttl=900, show_spinner=False)
def load_exports():
    required = {
        'Forecasts': OUT/'county_forecasts.csv',
        'Filing history': OUT/'county_month.csv',
        'Backtests': OUT/'rolling_backtests.csv',
        'Model performance': OUT/'model_metrics.csv',
        'Coverage audit': OUT/'data_quality.json',
    }
    absent = [str(p.relative_to(OUT.parent.parent)) for p in required.values() if not p.exists()]
    if absent:
        return None, absent
    inputs = {
        'forecasts':pd.read_csv(required['Forecasts'],dtype={'fips':'str','state_fips':'str'},
                                parse_dates=['month','last_observed_month','forecast_issue_month']),
        'history':pd.read_csv(required['Filing history'],dtype={'fips':'str'},parse_dates=['month']),
        'backtests':pd.read_csv(required['Backtests'],dtype={'fips':'str'},parse_dates=['month','origin_month']),
        'metrics':pd.read_csv(required['Model performance']),
        'audit':json.loads(required['Coverage audit'].read_text(encoding='utf-8')),
    }
    for key in ['history','forecasts','backtests']:
        inputs[key]['fips'] = inputs[key].fips.astype(str).str.zfill(5)
    return inputs, []


def make_map(d, geo):
    """Gray = no displayed, matched forecast; not a claim of zero filings."""
    feature_ids = [f['id'] for f in geo['features'] if 'id' in f]
    supported = set(feature_ids)
    shown = d[d.fips.isin(supported)].copy()
    fig = go.Figure()
    # Make all counties a neutral backdrop, so uncovered counties never look safe.
    fig.add_trace(go.Choropleth(
        geojson=geo, locations=feature_ids, z=[1]*len(feature_ids),
        colorscale=[[0,'#DDE2E7'],[1,'#DDE2E7']], zmin=0, zmax=1,
        showscale=False, name='No mapped forecast', showlegend=True,
        marker_line_width=.12, marker_line_color='white', hoverinfo='skip'))
    for category, color in MAP_COLORS.items():
        group = shown[shown.map_category == category]
        if group.empty: continue
        labels = group['county_name'].fillna('County '+group.fips)
        hover = [f'{name}<br>FIPS {fid}<br>Forecast: {value:.1f} filings / 1,000 renter households<br>Predicted filings: {count:,.0f}<br>{category}'
                 for name, fid, value, count in zip(labels,group.fips,group.predicted_rate_per_1000_renter_households,group.predicted_filings)]
        fig.add_trace(go.Choropleth(
            geojson=geo, locations=group.fips, z=[1]*len(group),
            zmin=0, zmax=1, colorscale=[[0,color],[1,color]],
            showscale=False, name=category, showlegend=True,
            text=hover, hovertemplate='%{text}<extra></extra>',
            marker_line_color='white', marker_line_width=.35))
    fig.update_geos(scope='usa', visible=False, showcoastlines=False, showland=True,
                    landcolor='white', bgcolor='rgba(0,0,0,0)', showsubunits=True,
                    subunitcolor='#B7C2CA', projection_type='albers usa')
    fig.update_layout(height=590, margin={'l':0,'r':0,'t':0,'b':0},
                      legend={'orientation':'h','y':-0.08,'x':0.02,'font':{'size':11}},
                      paper_bgcolor='white')
    return fig, len(shown), len(d)-len(shown)


def pct(x):
    return 'Unavailable' if pd.isna(x) else f'{100*float(x):.1f}%'

st.title('Evict-AI')
st.markdown('**An Early Warning and Decision Support System for Eviction Filings**')
st.caption('Observed county-level court filings: Legal Services Corporation  •  County housing and socioeconomic indicators: American Community Survey')
st.info('**Research prototype:** Maps show geographic patterns in *forecast filing rates*, not individual eviction probabilities. Alert thresholds are experimental and should not determine eligibility for assistance.')

payload, missing = load_exports()
if payload is None:
    st.subheader('Waiting for the first official-data run')
    st.warning('No real forecast results are available in this repository yet. The dashboard will populate only after the automated data and forecasting workflow finishes successfully.')
    st.markdown('**To activate this website:** 1. Upload this entire project to GitHub, including `.github/workflows`. 2. Add your `CENSUS_API_KEY` repository secret. 3. Open **Actions → Update eviction forecast data → Run workflow**. 4. Deploy `app.py` through Streamlit Community Cloud.')
    st.code('Missing processed outputs:\n'+'\n'.join(missing),language='text')
    st.markdown('**Verified public data sources:** [LSC eviction tracker](https://civilcourtdata.lsc.gov/data/eviction/) · [Census ACS API](https://api.census.gov/data.html). Check GitHub Actions logs if the official exports have changed their schema.')
    st.stop()

forecast, history, bt, metrics, audit = [payload[k] for k in ['forecasts','history','backtests','metrics','audit']]
valid_horizons = sorted(int(x) for x in forecast.horizon.dropna().unique())
if not valid_horizons:
    st.error('No validated forecast horizons in the dataset.'); st.stop()

with st.sidebar:
    st.header('Explore forecasts')
    horizon = st.radio('Lead time',valid_horizons,format_func=lambda x: f'{x} month'+('s' if x>1 else '')+' ahead')
    for_horizon = forecast[forecast.horizon==horizon].copy()
    for_horizon = prepare_map_categories(for_horizon)
    if 'county_name' not in for_horizon.columns:
        for_horizon['county_name'] = for_horizon.fips.map(
            history.drop_duplicates('fips').set_index('fips').get('NAME',pd.Series(dtype='object')))
    available_states = sorted(for_horizon.state_fips.dropna().unique())
    state_labels = {'All mapped states':'All'}
    state_labels.update({f'{NAME_OF_STATE.get(s,"State "+s)} ({s})':s for s in available_states})
    state_label = st.selectbox('State', list(state_labels))
    chosen_state = state_labels[state_label]
    chosen = for_horizon if chosen_state=='All' else for_horizon[for_horizon.state_fips==chosen_state]
    st.divider()
    st.caption('Map categories reflect current model outputs. They are not validated risk probabilities.')
    st.caption('Gray = no mapped forecast. This may reflect noncoverage, missing data, or outdated boundaries.')

if chosen.empty:
    st.warning('No mapped forecasts for this selection.'); st.stop()

latest = str(pd.to_datetime(chosen.month.max()).date())
issue = str(pd.to_datetime(chosen.forecast_issue_month.max()).date())
obs_end = audit.get('last_included_month','not recorded')
if pd.to_datetime(chosen.month.max()).to_period('M') < pd.Timestamp.now().to_period('M'):
    st.warning('These are currently historical forecast dates, not current alerts. The official court export may be delayed. Verify the data currency in the coverage tab.')
st.caption(f'Forecast target month: **{latest}** · Forecast issue month: **{issue}** · Latest retained LSC observation: **{obs_end}** · ACS values are delayed historical five-year estimates')

m1,m2,m3,m4 = st.columns(4)
m1.metric('Counties forecast',f'{chosen.fips.nunique():,}')
m2.metric('Experimental rising-filing alerts',f'{(chosen.map_category=="Emerging increase (experimental alert)").sum():,}')
m3.metric('Sum of predicted filings',f'{chosen.predicted_filings.sum():,.0f}')
m4.metric('Forecast horizon',f'{horizon} month'+('s' if horizon!=1 else ''))

t1,t2,t3,t4,t5 = st.tabs(['🗺️ County map', '📈 County details', '🏘️ Housing indicators', '🧪 Forecast accuracy', '📚 Coverage and methods'])
with t1:
    st.subheader('United States county filing forecast map')
    st.caption('Orange = experimental increase alert; red = tracked top quartile of forecast filing rate; teal = other tracked counties; gray = no mapped forecast. Red does not automatically imply an upward trend.')
    try:
        geo = load_shapes()
        figure,nmapped,unmapped = make_map(chosen,geo)
        st.plotly_chart(figure,use_container_width=True,config={'displaylogo':False})
        if unmapped:
            st.warning(f'{unmapped} forecast county identifier(s) could not be drawn using this map boundary file. Their numeric results remain in the table; see the coverage tab.')
    except Exception as exc:
        st.warning('County boundary download is unavailable right now. County forecasts and data tables remain usable. '+str(exc))
    ranks = chosen.sort_values('predicted_rate_per_1000_renter_households',ascending=False)
    displaycols=['county_name','fips','map_category','predicted_filings',
                 'predicted_rate_per_1000_renter_households','change_vs_12m_pct',
                 'rent_burden_30_share','acs_asof_year']
    st.dataframe(ranks[displaycols].rename(columns={
        'county_name':'County','fips':'County FIPS','map_category':'Map category',
        'predicted_filings':'Forecast filings',
        'predicted_rate_per_1000_renter_households':'Forecast filings per 1,000 renter households',
        'change_vs_12m_pct':'Change vs. 12-month mean (%)',
        'rent_burden_30_share':'Share of rent-paying renter households burdened (fraction)',
        'acs_asof_year':'ACS vintage'}),hide_index=True,use_container_width=True)
    st.download_button('Download county forecasts CSV',ranks.to_csv(index=False).encode(),
                       file_name=f'evict_ai_forecasts_{horizon}m.csv',mime='text/csv')

with t2:
    ids = chosen.copy()
    ids['display_name'] = ids['county_name'].fillna('Unknown county').astype(str) + '  ·  '+ids.fips
    label_to_fips = dict(zip(ids.display_name,ids.fips))
    selected_label = st.selectbox('Select a county for detailed history', sorted(label_to_fips),key='selected_county')
    fid = label_to_fips[selected_label]
    row = ids[ids.fips==fid].iloc[0]
    f1,f2,f3 = st.columns(3)
    f1.metric('Predicted filing count', f'{row.predicted_filings:,.1f}')
    f2.metric('Predicted filings / 1,000 renters',f'{row.predicted_rate_per_1000_renter_households:.2f}')
    f3.metric('Experimental category', row.map_category)
    observed = history[history.fips==fid].sort_values('month')
    if observed.empty:
        st.warning('No underlying history for this county.'); st.stop()
    fig = px.line(observed,x='month',y='filings',markers=True,
                  title=f'Observed monthly court filings — {selected_label}',
                  labels={'filings':'Observed filing count','month':'Filing month'})
    fig.add_hline(y=float(row.roll_12),line_dash='dash',annotation_text='Prior 12-month mean',
                  annotation_position='top left',line_color='#8E9AA7')
    fig.add_scatter(x=[row.month],y=[row.predicted_filings],mode='markers',
                    marker={'size':13,'symbol':'diamond','color':'#C13549'},name='Forecast (not observed)')
    fig.update_layout(height=410,legend={'orientation':'h','y':-0.28})
    st.plotly_chart(fig,use_container_width=True)
    st.caption('The red diamond is a model forecast; points in the historical line are observed court filings. The filing count may include multiple cases involving one household.')
    st.markdown('**Historical filings and forecast — download**')
    out = observed[['month','filings']].copy();out['source']='observed'; out = pd.concat([
        out,pd.DataFrame([{'month':row.month,'filings':row.predicted_filings,'source':'forecast'}])],ignore_index=True)
    st.download_button('Download selected county series',out.to_csv(index=False).encode(),
                       file_name=f'county_{fid}_history_forecast.csv',mime='text/csv')

with t3:
    st.subheader('Housing and economic context from the ACS')
    st.caption('County ACS five-year indicators are not monthly measurements. Housing indicators are predictors or context, not proof of what caused filings.')
    a,b = st.columns(2)
    with a:
        chart = chosen.dropna(subset=['rent_burden_30_share']).nlargest(20,'rent_burden_30_share').copy()
        chart['Rent-burdened renter households (%)'] = 100*chart.rent_burden_30_share
        fig = px.bar(chart.sort_values('Rent-burdened renter households (%)'),
                     x='Rent-burdened renter households (%)',y='county_name',orientation='h',
                     title='Counties with the highest ACS rent burden (among tracked counties)',
                     labels={'county_name':''})
        fig.update_layout(height=560)
        st.plotly_chart(fig,use_container_width=True)
    with b:
        scatter = chosen.dropna(subset=['rent_burden_30_share','predicted_rate_per_1000_renter_households']).copy()
        scatter['Rent burden (%)']=100*scatter.rent_burden_30_share
        fig = px.scatter(scatter,x='Rent burden (%)',y='predicted_rate_per_1000_renter_households',
                         hover_name='county_name',hover_data=['fips','acs_asof_year'],
                         title='ACS rent burden and predicted filing rate',
                         labels={'predicted_rate_per_1000_renter_households':'Predicted filings per 1,000 renter households'},
                         opacity=.75)
        fig.update_layout(height=560)
        st.plotly_chart(fig,use_container_width=True)
    st.markdown('**Available predictors** include renter share, rent burden, severe rent burden, vacancy, median contract rent, median household income, poverty, unemployment, SNAP receipt and house heating fuel composition. Heating fuel is **not** a measure of energy bills, energy prices, or energy burden.')
    st.caption('ACS estimates have sampling uncertainty. This prototype does not yet incorporate their margins of error into predictive uncertainty.')

with t4:
    st.subheader('Do the forecasts improve on simpler models?')
    st.caption('Genuine rolling-origin historical tests: each evaluated target month is later than the data used to fit the model. All methods use the same filtered county-months.')
    test = bt.loc[(bt.horizon==horizon)&(bt.fips.isin(chosen.fips))].copy()
    if test.empty:
        st.warning('No historical tests for this selection.')
    else:
        score = retrospective_metrics(test)
        st.dataframe(score,hide_index=True,use_container_width=True)
        if not score.empty:
            fig=px.bar(score,x='Model',y='WAPE (%)',title='Weighted absolute percentage error (lower is better)',
                       text_auto='.1f',color='Model')
            fig.update_layout(showlegend=False,height=350)
            st.plotly_chart(fig,use_container_width=True)
        monthly = (test.groupby('month',as_index=False)[['filings','model_history_acs','model_history',
                              'baseline_last','baseline_seasonal']].sum(min_count=1))
        fig=px.line(monthly,x='month',y=['filings','model_history_acs','model_history',
                                       'baseline_last','baseline_seasonal'],markers=True,
                    title='Observed versus predicted monthly filing totals in held-out periods',
                    labels={'value':'Monthly filings','month':'Test month','variable':'Series'})
        fig.update_layout(height=430)
        st.plotly_chart(fig,use_container_width=True)
        quality=alert_quality(test)
        if quality:
            st.markdown('**Experimental rising-filings alert performance (held-out months)**')
            st.json(quality)
        st.download_button('Download held-out predictions',test.to_csv(index=False).encode(),
                           file_name=f'evict_ai_backtests_{horizon}m.csv',mime='text/csv')
        st.warning('An ACS-augmented model is not automatically stronger: it must outperform the filings-only and seasonal alternatives on later months. These are forecasts, not causal estimates or a like-for-like Berkeley HPRM evaluation.')

with t5:
    st.subheader('Data coverage and research safeguards')
    c1,c2,c3=st.columns(3)
    c1.metric('Counties in complete LSC/ACS panel',str(audit.get('included_counties','—')))
    c2.metric('States with linked counties',str(audit.get('included_states','—')))
    c3.metric('Unmatched or noncounty source records',str(audit.get('unmatched_or_noncounty_records','—')))
    st.markdown('**Source and coverage audit**')
    st.json(audit)
    st.markdown('''**Interpretation.** Eviction filings are court cases, not completed evictions or unique displaced households. Jurisdictions differ in law, case classification and reporting. Some LSC data are missing or revised later; missing is never treated as zero. Colors outside the modeled sample are neutral gray, not zero risk.

**Forecasts.** The current model uses a conservative reporting delay and historically eligible ACS vintages. The one- and three-month labels are forecast horizons after an assumed data-availability cutoff, not a promise of alerts a full three months before actual court proceedings. Prediction uncertainty and revision-adjusted real-time evaluation are still open tasks.

**Limitations.** County geography loses within-county variation. The boundary display uses a public Plotly county GeoJSON that may not match modern county-equivalent boundary changes in every jurisdiction. County identifiers that cannot be mapped remain available in the table. Do not make decisions about individuals from these county forecasts.

**References.** [LSC Civil Court Data Initiative](https://civilcourtdata.lsc.gov/data/eviction/) · [Census ACS](https://www.census.gov/programs-surveys/acs) · [GitHub Plotly county boundaries](https://github.com/plotly/datasets/blob/master/geojson-counties-fips.json) · [UC Berkeley HPRM](https://evictionresearch.net/hprm/).''')
