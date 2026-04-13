from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import jax
import jax.numpy as jnp
import numpy as np
import numpyro
import numpyro.distributions as dist
import pandas as pd
from numpyro.infer import MCMC, NUTS, Predictive

numpyro.enable_x64()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / 'app' / 'data'
RAW_DIR = DATA_DIR / 'raw'

E_PATH = RAW_DIR / 'SSDSE-E-2025.csv'
B_PATH = RAW_DIR / 'SSDSE-B-2025.csv'
GEO_PATH = RAW_DIR / 'prefectures.json'

METRICS_PATH = DATA_DIR / 'region_metrics.json'
REGIONS_PATH = DATA_DIR / 'regions.geojson'
MODEL_INFO_PATH = DATA_DIR / 'model_info.json'

FEATURE_COLUMNS = [
    'aging_rate',
    'child_rate',
    'birth_rate',
    'death_rate',
    'net_migration_rate',
    'hospital_density',
    'clinic_density',
    'daycare_coverage',
]

PREF_CODE_TO_NAME = {
    '01': 'Hokkaido', '02': 'Aomori Prefecture', '03': 'Iwate Prefecture', '04': 'Miyagi Prefecture', '05': 'Akita Prefecture', '06': 'Yamagata Prefecture', '07': 'Fukushima Prefecture',
    '08': 'Ibaraki Prefecture', '09': 'Tochigi Prefecture', '10': 'Gunma Prefecture', '11': 'Saitama Prefecture', '12': 'Chiba Prefecture', '13': 'Tokyo Metropolis', '14': 'Kanagawa Prefecture',
    '15': 'Niigata Prefecture', '16': 'Toyama Prefecture', '17': 'Ishikawa Prefecture', '18': 'Fukui Prefecture', '19': 'Yamanashi Prefecture', '20': 'Nagano Prefecture', '21': 'Gifu Prefecture',
    '22': 'Shizuoka Prefecture', '23': 'Aichi Prefecture', '24': 'Mie Prefecture', '25': 'Shiga Prefecture', '26': 'Kyoto Prefecture', '27': 'Osaka Prefecture', '28': 'Hyogo Prefecture',
    '29': 'Nara Prefecture', '30': 'Wakayama Prefecture', '31': 'Tottori Prefecture', '32': 'Shimane Prefecture', '33': 'Okayama Prefecture', '34': 'Hiroshima Prefecture', '35': 'Yamaguchi Prefecture',
    '36': 'Tokushima Prefecture', '37': 'Kagawa Prefecture', '38': 'Ehime Prefecture', '39': 'Kochi Prefecture', '40': 'Fukuoka Prefecture', '41': 'Saga Prefecture', '42': 'Nagasaki Prefecture',
    '43': 'Kumamoto Prefecture', '44': 'Oita Prefecture', '45': 'Miyazaki Prefecture', '46': 'Kagoshima Prefecture', '47': 'Okinawa Prefecture'
}


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def zscore(series: pd.Series, invert: bool = False) -> pd.Series:
    numeric = pd.to_numeric(series, errors='coerce')
    spread = float(numeric.std(ddof=0))
    if spread == 0 or np.isnan(spread):
        vals = pd.Series(np.zeros(len(numeric)), index=numeric.index)
    else:
        vals = (numeric - float(numeric.mean())) / spread
    vals = 1 / (1 + np.exp(-vals))
    if invert:
        vals = 1 - vals
    return vals.clip(0, 1)


def load_ssdse_e() -> pd.DataFrame:
    df = pd.read_csv(E_PATH, encoding='cp932')
    data = df.iloc[2:].copy().reset_index(drop=True)
    data.rename(columns={'SSDSE-E-2025': 'region_code_raw', 'Prefecture': 'region_name'}, inplace=True)
    numeric_columns = [c for c in data.columns if c not in {'region_code_raw', 'region_name'}]
    for col in numeric_columns:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    data['region_code'] = data['region_code_raw'].str.extract(r'R(\d{2})')[0]
    data = data[data['region_code'].isin(PREF_CODE_TO_NAME.keys())].copy()
    return data


def load_ssdse_b() -> pd.DataFrame:
    df = pd.read_csv(B_PATH, encoding='cp932')
    data = df.iloc[1:].copy().reset_index(drop=True)
    data.rename(columns={'SSDSE-B-2025': 'year', 'Code': 'region_code_raw', 'Prefecture': 'region_name'}, inplace=True)
    data['year'] = pd.to_numeric(data['year'], errors='coerce').astype('Int64')
    data['region_code'] = data['region_code_raw'].str.extract(r'R(\d{2})')[0]
    data = data[data['region_code'].isin(PREF_CODE_TO_NAME.keys())].copy()
    numeric_columns = [c for c in data.columns if c not in {'year', 'region_code_raw', 'region_name', 'region_code'}]
    for col in numeric_columns:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    return data


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    total = out['A1101'].replace(0, np.nan)
    child = out['A1301'].replace(0, np.nan)

    out['aging_rate'] = out['A1303'] / total
    out['child_rate'] = out['A1301'] / total
    out['birth_rate'] = out['A4101'] / total
    out['death_rate'] = out['A4200'] / total
    out['net_migration_rate'] = (out['A5101'] - out['A5102']) / total
    out['hospital_density'] = out['I510120'] / total * 100_000
    out['clinic_density'] = out['I5102'] / total * 100_000
    out['daycare_coverage'] = out['J2506'] / child
    return out


def bayesian_decline_model(X: jnp.ndarray, y: jnp.ndarray | None = None) -> None:
    n_features = X.shape[1]
    intercept = numpyro.sample('intercept', dist.Normal(0.005, 0.01))
    beta_scale = numpyro.sample('beta_scale', dist.HalfNormal(0.01))
    beta = numpyro.sample('beta', dist.Normal(jnp.zeros(n_features), beta_scale))
    sigma = numpyro.sample('sigma', dist.HalfNormal(0.01))
    mu = intercept + jnp.matmul(X, beta)
    numpyro.deterministic('mu', mu)
    numpyro.sample('obs', dist.Normal(mu, sigma), obs=y)


def summarize_array(values: np.ndarray) -> Dict[str, float]:
    return {
        'mean': float(np.mean(values)),
        'sd': float(np.std(values, ddof=0)),
        'p05': float(np.quantile(values, 0.05)),
        'p50': float(np.quantile(values, 0.50)),
        'p95': float(np.quantile(values, 0.95)),
    }


def fit_decline_model(panel: pd.DataFrame) -> Dict[str, Any]:
    frame = add_derived_features(panel)
    frame = frame.sort_values(['region_code', 'year']).copy()
    frame['next_population'] = frame.groupby('region_code')['A1101'].shift(-1)
    train = frame.dropna(subset=FEATURE_COLUMNS + ['next_population']).copy()
    train['target_decline_rate'] = (train['A1101'] - train['next_population']) / train['A1101']

    X = train[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = train['target_decline_rate'].to_numpy(dtype=float)

    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds[stds == 0] = 1.0
    Xs = (X - means) / stds

    X_jnp = jnp.asarray(Xs)
    y_jnp = jnp.asarray(y)

    kernel = NUTS(bayesian_decline_model, target_accept_prob=0.9)
    mcmc = MCMC(kernel, num_warmup=600, num_samples=800, num_chains=1, progress_bar=False)
    mcmc.run(jax.random.PRNGKey(42), X=X_jnp, y=y_jnp)
    posterior_samples = mcmc.get_samples()

    predictive_train = Predictive(bayesian_decline_model, posterior_samples=posterior_samples)
    train_draws = np.asarray(predictive_train(jax.random.PRNGKey(43), X=X_jnp)['obs'])
    train_pred_mean = train_draws.mean(axis=0)
    residuals = y - train_pred_mean
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals**2)))
    denom = float(np.sum((y - y.mean()) ** 2))
    r2 = float(1 - (np.sum(residuals**2) / denom)) if denom > 0 else 0.0

    latest = add_derived_features(panel[panel['year'] == panel['year'].max()].copy())
    X_latest = latest[FEATURE_COLUMNS].to_numpy(dtype=float)
    X_latest_s = (X_latest - means) / stds
    X_latest_jnp = jnp.asarray(X_latest_s)

    predictive_latest = Predictive(bayesian_decline_model, posterior_samples=posterior_samples)
    latest_draws = np.asarray(predictive_latest(jax.random.PRNGKey(44), X=X_latest_jnp)['obs'])

    latest_pred_mean = latest_draws.mean(axis=0)
    latest_p10 = np.quantile(latest_draws, 0.10, axis=0)
    latest_p50 = np.quantile(latest_draws, 0.50, axis=0)
    latest_p90 = np.quantile(latest_draws, 0.90, axis=0)
    latest_std = latest_draws.std(axis=0)

    latest['predicted_annual_decline_rate'] = np.clip(latest_pred_mean, -0.01, 0.04)
    latest['prediction_p10'] = np.clip(latest_p10, -0.01, 0.04)
    latest['prediction_p50'] = np.clip(latest_p50, -0.01, 0.04)
    latest['prediction_p90'] = np.clip(latest_p90, -0.01, 0.04)
    latest['prediction_std'] = np.clip(latest_std, 0.0001, 0.03)
    latest['prediction_interval'] = latest['prediction_p90'] - latest['prediction_p10']

    coefficient_summary = {'intercept': summarize_array(np.asarray(posterior_samples['intercept']))}
    beta_draws = np.asarray(posterior_samples['beta'])
    for idx, name in enumerate(FEATURE_COLUMNS):
        coefficient_summary[name] = summarize_array(beta_draws[:, idx])

    sigma_summary = summarize_array(np.asarray(posterior_samples['sigma']))
    beta_scale_summary = summarize_array(np.asarray(posterior_samples['beta_scale']))

    return {
        'latest_predictions': latest[[
            'region_code',
            'predicted_annual_decline_rate',
            'prediction_p10',
            'prediction_p50',
            'prediction_p90',
            'prediction_std',
            'prediction_interval',
        ]].copy(),
        'model_info': {
            'model_name': 'bayesian_linear_regression_numpyro',
            'target': 'next_year_population_decline_rate',
            'features': FEATURE_COLUMNS,
            'sample_count': int(len(train)),
            'train_years': [int(train['year'].min()), int(train['year'].max())],
            'performance': {'mae': mae, 'rmse': rmse, 'r2': r2},
            'posterior': {
                'sigma': sigma_summary,
                'beta_scale': beta_scale_summary,
                'coefficients': coefficient_summary,
            },
            'inference': {
                'engine': 'NumPyro NUTS',
                'num_warmup': 600,
                'num_samples': 800,
                'num_chains': 1,
                'seed': 42,
            },
            'scaling': {
                'feature_means': {name: float(value) for name, value in zip(FEATURE_COLUMNS, means)},
                'feature_stds': {name: float(value) for name, value in zip(FEATURE_COLUMNS, stds)},
            },
            'note': 'Learn next-year population decline rates from prefecture-level SSDSE-B time series using Bayesian linear regression with NumPyro + JAX, then apply posterior predictive estimates to the 2023 cross section to project the 2035 population.',
        },
    }


def build_metrics(latest_snapshot: pd.DataFrame, predictions: pd.DataFrame) -> List[Dict[str, Any]]:
    df = latest_snapshot.merge(predictions, on='region_code', how='left')

    df['aging_rate'] = (df['A1303'] / df['A1101']).clip(0, 1)
    df['vacancy_rate'] = (df['H110202'] / df['H1100']).clip(0, 1)
    df['foreign_share'] = (df['A1700'] / df['A1101']).fillna(0).clip(0, 1)
    df['net_migration_rate'] = ((df['A5101'] - df['A5102']) / df['A1101']).fillna(0)
    df['childcare_access_score'] = (
        0.55 * zscore(df['J2506'] / df['A1301'].replace(0, np.nan))
        + 0.25 * zscore(df['J2503'] / df['A1301'].replace(0, np.nan) * 1_000)
        + 0.20 * zscore(df['E1501'] / df['A1301'].replace(0, np.nan))
    ).clip(0, 1)

    df['medical_access_risk'] = (
        0.40 * zscore(df['I6100'] / df['A1101'] * 100_000, invert=True)
        + 0.25 * zscore(df['I5102'] / df['A1101'] * 100_000, invert=True)
        + 0.15 * zscore(df['I510120'] / df['A1101'] * 100_000, invert=True)
        + 0.10 * zscore(df['A1101'] / df['B1103'].replace(0, np.nan), invert=True)
        + 0.10 * zscore(df['aging_rate'])
    ).clip(0, 1)

    years_ahead = 12
    annual_decline = df['predicted_annual_decline_rate'].fillna(0.008).clip(-0.005, 0.03)
    annual_decline_p10 = df['prediction_p10'].fillna(annual_decline).clip(-0.005, 0.03)
    annual_decline_p50 = df['prediction_p50'].fillna(annual_decline).clip(-0.005, 0.03)
    annual_decline_p90 = df['prediction_p90'].fillna(annual_decline).clip(-0.005, 0.03)

    df['population_2020'] = df['A1101'].astype(int)
    df['population_2035'] = (df['population_2020'] * np.power(1 - annual_decline, years_ahead)).round().astype(int)
    df['population_2035_p10'] = (df['population_2020'] * np.power(1 - annual_decline_p10, years_ahead)).round().astype(int)
    df['population_2035_p50'] = (df['population_2020'] * np.power(1 - annual_decline_p50, years_ahead)).round().astype(int)
    df['population_2035_p90'] = (df['population_2020'] * np.power(1 - annual_decline_p90, years_ahead)).round().astype(int)

    decline_fraction = 1 - (df['population_2035'] / df['population_2020'].replace(0, np.nan))
    df['depopulation_index'] = (0.75 * decline_fraction + 0.25 * zscore(-df['net_migration_rate'])).clip(0, 1)

    df['energy_price_shock'] = (
        0.50 * zscore(df['A1101'] / df['B1103'].replace(0, np.nan), invert=True)
        + 0.30 * zscore(df['medical_access_risk'])
        + 0.20 * zscore(df['vacancy_rate'])
    ).clip(0, 1)
    df['food_price_shock'] = (
        0.45 * zscore(df['L3221'] / df['C122101'].replace(0, np.nan))
        + 0.35 * zscore(df['aging_rate'])
        + 0.20 * zscore(df['childcare_access_score'], invert=True)
    ).clip(0, 1)
    df['service_capacity_pressure'] = (
        0.40 * zscore(df['foreign_share'])
        + 0.35 * zscore(df['vacancy_rate'], invert=True)
        + 0.25 * zscore(df['medical_access_risk'])
    ).clip(0, 1)

    recency_penalty = 0.03
    df['data_quality_score'] = (0.88 - recency_penalty - 0.10 * zscore(df['vacancy_rate']) - 0.08 * zscore(df['foreign_share'])).clip(0.45, 0.95)
    df['model_uncertainty'] = (df['prediction_std'].fillna(0.003) * 12.0 + df['prediction_interval'].fillna(0.01) * 2.5 + 0.01).clip(0.02, 0.25)
    df['external_volatility'] = (0.5 * df['energy_price_shock'] + 0.3 * df['food_price_shock'] + 0.2 * df['service_capacity_pressure']).clip(0, 1)

    records: List[Dict[str, Any]] = []
    for _, row in df.sort_values('region_code').iterrows():
        records.append(
            {
                'region_code': row['region_code'],
                'region_name': row['region_name'],
                'population_2020': int(row['population_2020']),
                'population_2035': int(row['population_2035']),
                'population_2035_p10': int(row['population_2035_p10']),
                'population_2035_p50': int(row['population_2035_p50']),
                'population_2035_p90': int(row['population_2035_p90']),
                'aging_rate': round(float(row['aging_rate']), 4),
                'vacancy_rate': round(float(row['vacancy_rate']), 4),
                'depopulation_index': round(float(row['depopulation_index']), 4),
                'medical_access_risk': round(float(row['medical_access_risk']), 4),
                'childcare_access_score': round(float(row['childcare_access_score']), 4),
                'energy_price_shock': round(float(row['energy_price_shock']), 4),
                'food_price_shock': round(float(row['food_price_shock']), 4),
                'service_capacity_pressure': round(float(row['service_capacity_pressure']), 4),
                'data_quality_score': round(float(row['data_quality_score']), 4),
                'model_uncertainty': round(float(row['model_uncertainty']), 4),
                'external_volatility': round(float(row['external_volatility']), 4),
                'predicted_annual_decline_rate': round(float(row['predicted_annual_decline_rate']), 5),
                'prediction_p10': round(float(row['prediction_p10']), 5),
                'prediction_p50': round(float(row['prediction_p50']), 5),
                'prediction_p90': round(float(row['prediction_p90']), 5),
                'prediction_std': round(float(row['prediction_std']), 5),
                'prediction_interval': round(float(row['prediction_interval']), 5),
                'source_years': {
                    'population': 2023,
                    'housing': 2023,
                    'medical': 2022,
                    'childcare': 2022,
                    'model_train_start': 2011,
                    'model_train_end': 2022,
                },
            }
        )
    return records


def build_regions_geojson(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    raw = json.loads(GEO_PATH.read_text(encoding='utf-8'))
    name_to_code = {m['region_name']: m['region_code'] for m in metrics}
    features = []
    for feature in raw['features']:
        name = feature['properties'].get('N03_001')
        code = name_to_code.get(name)
        if not code:
            continue
        features.append(
            {
                'type': 'Feature',
                'properties': {
                    'region_code': code,
                    'region_name': name,
                },
                'geometry': feature['geometry'],
            }
        )
    return {'type': 'FeatureCollection', 'features': features}


def main() -> None:
    e = load_ssdse_e()
    b = load_ssdse_b()
    model = fit_decline_model(b)
    metrics = build_metrics(e, model['latest_predictions'])
    regions = build_regions_geojson(metrics)

    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    REGIONS_PATH.write_text(json.dumps(regions, ensure_ascii=False), encoding='utf-8')

    raw_metadata = {}
    metadata_path = RAW_DIR / 'source_metadata.json'
    if metadata_path.exists():
        raw_metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    model_info = model['model_info']
    model_info['sources'] = raw_metadata.get('sources', [])
    MODEL_INFO_PATH.write_text(json.dumps(model_info, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'Wrote {METRICS_PATH}')
    print(f'Wrote {REGIONS_PATH}')
    print(f'Wrote {MODEL_INFO_PATH}')


if __name__ == '__main__':
    main()
