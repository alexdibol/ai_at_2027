from AlgorithmImports import *
from strategy_config import *

import json
import hashlib
from datetime import datetime

import numpy as np
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import balanced_accuracy_score


def stable_hash(value):
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IndependentRiskGovernor:
    """
    Logically independent risk review.
    It does not fit models and does not choose the research champion.
    It receives candidate weights and can clamp or halt them.
    """

    def __init__(self):
        self.peak_value = None
        self.halted = False
        self.last_report = {}

    def review(self, algorithm, candidate_weights):
        value = float(algorithm.portfolio.total_portfolio_value)

        if self.peak_value is None:
            self.peak_value = value
        self.peak_value = max(self.peak_value, value)

        drawdown = 0.0 if self.peak_value <= 0 else value / self.peak_value - 1.0
        if drawdown <= -MAX_PORTFOLIO_DRAWDOWN:
            self.halted = True

        if self.halted:
            self.last_report = {
                "status": "HALT",
                "portfolio_value": value,
                "drawdown": drawdown,
                "reason": "portfolio_drawdown_limit",
            }
            return {}

        bounded = {}
        for symbol, weight in candidate_weights.items():
            bounded[symbol] = float(
                max(-MAX_POSITION_WEIGHT, min(MAX_POSITION_WEIGHT, weight))
            )

        # Sector concentration control.
        for sector, symbols in algorithm._symbols_by_sector.items():
            sector_symbols = [s for s in symbols if s in bounded]
            sector_gross = sum(abs(bounded[s]) for s in sector_symbols)
            if sector_gross > MAX_SECTOR_GROSS and sector_gross > 0:
                scale = MAX_SECTOR_GROSS / sector_gross
                for s in sector_symbols:
                    bounded[s] *= scale

        gross = sum(abs(w) for w in bounded.values())
        if gross > MAX_GROSS and gross > 0:
            scale = MAX_GROSS / gross
            bounded = {s: w * scale for s, w in bounded.items()}

        self.last_report = {
            "status": "PASS",
            "portfolio_value": value,
            "drawdown": drawdown,
            "gross": sum(abs(w) for w in bounded.values()),
            "net": sum(bounded.values()),
            "positions": len([w for w in bounded.values() if abs(w) > 1e-12]),
        }
        return bounded


class GovernedQuantConnectBridge(QCAlgorithm):
    """
    NB07 QuantConnect/LEAN bridge.

    The algorithm is intentionally research-only. The LLM/control plane is external
    to this runtime. LEAN receives only deterministic configuration and code.
    """

    def initialize(self):
        if self.live_mode or LIVE_TRADING_AUTHORIZED or DEPLOYMENT_AUTHORIZED:
            raise RuntimeError(
                "NB07 governance denial: live trading/deployment is not authorized."
            )

        self.set_start_date(*START_DATE)
        self.set_end_date(*END_DATE)
        self.set_cash(STARTING_CASH)

        self._audit = []
        self._event_dates = {}
        self._model_diagnostics = []
        self._champion_name = None
        self._champion_model = None
        self._champion_kind = None
        self._risk = IndependentRiskGovernor()

        self._benchmark_symbol = self.add_equity(
            BENCHMARK,
            Resolution.DAILY,
            data_normalization_mode=DataNormalizationMode.ADJUSTED
        ).symbol
        self.set_benchmark(self._benchmark_symbol)

        self._symbols = []
        self._sector_by_symbol = {}
        self._symbols_by_sector = {}

        for sector, tickers in UNIVERSE_BY_SECTOR.items():
            sector_symbols = []
            for ticker in tickers:
                security = self.add_equity(
                    ticker,
                    Resolution.DAILY,
                    data_normalization_mode=DataNormalizationMode.ADJUSTED
                )
                security.set_fee_model(ConstantFeeModel(PER_ORDER_FEE_USD))
                security.set_slippage_model(
                    VolumeShareSlippageModel(
                        VOLUME_SHARE_LIMIT,
                        VOLUME_SHARE_PRICE_IMPACT
                    )
                )
                symbol = security.symbol
                self._symbols.append(symbol)
                sector_symbols.append(symbol)
                self._sector_by_symbol[symbol] = sector
                self._event_dates[symbol] = {
                    "dividend": None,
                    "split": None,
                }
            self._symbols_by_sector[sector] = sector_symbols

        self.set_warm_up(WARMUP_BARS, Resolution.DAILY)

        # Model training runs inside LEAN's training mechanism.
        self.train(
            self.date_rules.month_start(self._benchmark_symbol),
            self.time_rules.before_market_open(self._benchmark_symbol, 60),
            self._train_models,
        )

        # Portfolio rebalance follows training on the same monthly schedule.
        self.schedule.on(
            self.date_rules.month_start(self._benchmark_symbol),
            self.time_rules.after_market_open(self._benchmark_symbol, 30),
            self._rebalance,
        )

        self._record(
            "INITIALIZED",
            {
                "universe_size": len(self._symbols),
                "model_families": MODEL_FAMILIES,
                "portfolio_method": PORTFOLIO_METHOD,
                "research_only": RESEARCH_ONLY,
            },
        )

    def _record(self, event_type, payload):
        record = {
            "time": str(self.time),
            "event_type": event_type,
            "payload": payload,
        }
        record["hash"] = stable_hash(record)
        self._audit.append(record)

    def _build_model(self, name):
        if name == "logistic_regression":
            return (
                Pipeline([
                    ("scale", StandardScaler()),
                    ("model", LogisticRegression(
                        max_iter=500,
                        random_state=SEED,
                    )),
                ]),
                "classification",
            )
        if name == "knn":
            return (
                Pipeline([
                    ("scale", StandardScaler()),
                    ("model", KNeighborsClassifier(
                        n_neighbors=9,
                        weights="distance",
                    )),
                ]),
                "classification",
            )
        if name == "random_forest":
            return (
                RandomForestClassifier(
                    n_estimators=160,
                    max_depth=6,
                    min_samples_leaf=12,
                    random_state=SEED,
                    n_jobs=1,
                ),
                "classification",
            )
        if name == "mlp":
            return (
                Pipeline([
                    ("scale", StandardScaler()),
                    ("model", MLPClassifier(
                        hidden_layer_sizes=(24, 12),
                        max_iter=180,
                        early_stopping=True,
                        random_state=SEED,
                    )),
                ]),
                "classification",
            )
        if name == "linear_regression":
            return (
                Pipeline([
                    ("scale", StandardScaler()),
                    ("model", LinearRegression()),
                ]),
                "regression",
            )
        raise ValueError(f"Unknown approved model family: {name}")

    def _feature_frame_for_symbol(self, frame):
        frame = frame.sort_index().copy()
        close = frame["close"].astype(float)
        volume = frame["volume"].astype(float).replace(0, np.nan)
        dollar_volume = (close * volume).replace(0, np.nan)

        out = pd.DataFrame(index=frame.index)
        out["ret_1"] = close.pct_change(1)
        out["mom_5"] = close.pct_change(5)
        out["mom_20"] = close.pct_change(20)
        out["vol_20"] = close.pct_change().rolling(20).std()
        out["vol_60"] = close.pct_change().rolling(60).std()

        vol_mean = volume.rolling(20).mean()
        vol_std = volume.rolling(20).std().replace(0, np.nan)
        out["volume_z20"] = (volume - vol_mean) / vol_std

        dv_mean = dollar_volume.rolling(20).mean()
        dv_std = dollar_volume.rolling(20).std().replace(0, np.nan)
        out["dollar_volume_z20"] = (dollar_volume - dv_mean) / dv_std

        out["ma_ratio_20"] = close / close.rolling(20).mean() - 1.0
        out["ma_ratio_50"] = close / close.rolling(50).mean() - 1.0

        out["label_return_1"] = close.pct_change().shift(-1)
        out["label_up"] = (out["label_return_1"] > 0).astype(int)
        return out

    def _build_training_dataset(self):
        history = self.history(
            self._symbols,
            TRAINING_LOOKBACK_BARS,
            Resolution.DAILY,
        )
        if history is None or history.empty:
            return pd.DataFrame()

        parts = []
        for symbol in self._symbols:
            try:
                frame = history.loc[symbol]
            except Exception:
                continue

            if frame is None or len(frame) < 80:
                continue

            features = self._feature_frame_for_symbol(frame)
            features["symbol"] = str(symbol)
            features["event_time"] = features.index
            features = features.dropna(
                subset=FEATURES + ["label_return_1"]
            )
            parts.append(features)

        if not parts:
            return pd.DataFrame()

        dataset = pd.concat(parts, axis=0)
        return dataset.sort_values("event_time").reset_index(drop=True)

    def _train_models(self):
        if self.live_mode:
            raise RuntimeError("NB07 governance denial: live execution is prohibited.")
        if self.is_warming_up:
            return

        dataset = self._build_training_dataset()
        if dataset.empty or len(dataset) < 500:
            self._record("TRAIN_SKIPPED", {"rows": int(len(dataset))})
            return

        cut = int(len(dataset) * 0.80)
        train = dataset.iloc[:cut].copy()
        valid = dataset.iloc[cut:].copy()

        X_train = train[FEATURES].values
        X_valid = valid[FEATURES].values
        y_train_up = train["label_up"].astype(int).values
        y_valid_up = valid["label_up"].astype(int).values
        y_train_return = train["label_return_1"].astype(float).values

        diagnostics = []
        candidates = []

        for complexity, name in enumerate(MODEL_FAMILIES):
            model, kind = self._build_model(name)
            try:
                if kind == "classification":
                    model.fit(X_train, y_train_up)
                    pred_up = model.predict(X_valid).astype(int)
                else:
                    model.fit(X_train, y_train_return)
                    pred_return = model.predict(X_valid).astype(float)
                    pred_up = (pred_return > 0).astype(int)

                score = float(balanced_accuracy_score(y_valid_up, pred_up))
                diagnostics.append({
                    "model": name,
                    "kind": kind,
                    "validation_balanced_accuracy": score,
                    "complexity_rank": complexity,
                })
                candidates.append(
                    (score, -complexity, name, model, kind)
                )
            except Exception as exc:
                diagnostics.append({
                    "model": name,
                    "status": "FAILED",
                    "error": str(exc),
                    "complexity_rank": complexity,
                })

        if not candidates:
            self._record("TRAIN_FAILED", {"diagnostics": diagnostics})
            return

        # Deterministic champion selection.
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        score, _, name, model, kind = candidates[0]

        self._champion_name = name
        self._champion_model = model
        self._champion_kind = kind
        self._model_diagnostics = diagnostics

        self._record(
            "CHAMPION_SELECTED",
            {
                "champion": name,
                "kind": kind,
                "validation_balanced_accuracy": score,
                "diagnostics": diagnostics,
            },
        )

    def _latest_features(self):
        history = self.history(
            self._symbols,
            max(80, WARMUP_BARS),
            Resolution.DAILY,
        )
        if history is None or history.empty:
            return pd.DataFrame()

        rows = []
        for symbol in self._symbols:
            try:
                frame = history.loc[symbol]
            except Exception:
                continue

            if frame is None or len(frame) < 65:
                continue

            features = self._feature_frame_for_symbol(frame)
            latest = features.iloc[-1]
            if latest[FEATURES].isna().any():
                continue

            row = latest[FEATURES].to_dict()
            row["symbol_object"] = symbol
            rows.append(row)

        return pd.DataFrame(rows)

    def _recent_corporate_action(self, symbol):
        dates = self._event_dates.get(symbol, {})
        for event_date in dates.values():
            if event_date is None:
                continue
            if (self.time.date() - event_date).days <= EVENT_COOLDOWN_DAYS:
                return True
        return False

    def _model_scores(self, latest):
        X = latest[FEATURES].values
        if self._champion_kind == "classification":
            if hasattr(self._champion_model, "predict_proba"):
                probability = self._champion_model.predict_proba(X)[:, 1]
                return probability - 0.5
            return self._champion_model.predict(X).astype(float) - 0.5
        return self._champion_model.predict(X).astype(float)

    def _portfolio_weights(self, latest):
        scores = self._model_scores(latest)
        records = []

        for i, row in latest.iterrows():
            symbol = row["symbol_object"]
            if self._recent_corporate_action(symbol):
                continue
            records.append({
                "symbol": symbol,
                "score": float(scores[i]),
                "vol": max(float(row["vol_20"]), 1e-6),
            })

        if len(records) < 6:
            return {}

        records.sort(key=lambda x: x["score"])
        n_long = max(1, int(len(records) * LONG_FRACTION))
        n_short = max(1, int(len(records) * SHORT_FRACTION))

        short_side = records[:n_short]
        long_side = records[-n_long:]

        weights = {}

        if PORTFOLIO_METHOD == "equal_weight":
            for r in long_side:
                weights[r["symbol"]] = 0.5 / len(long_side)
            for r in short_side:
                weights[r["symbol"]] = -0.5 / len(short_side)

        else:
            # inverse-volatility / risk-parity proxy
            long_inv = np.array([1.0 / r["vol"] for r in long_side], dtype=float)
            short_inv = np.array([1.0 / r["vol"] for r in short_side], dtype=float)
            long_inv = long_inv / long_inv.sum()
            short_inv = short_inv / short_inv.sum()

            for r, w in zip(long_side, long_inv):
                weights[r["symbol"]] = float(0.5 * w)
            for r, w in zip(short_side, short_inv):
                weights[r["symbol"]] = float(-0.5 * w)

            if PORTFOLIO_METHOD == "volatility_target":
                approx_vol = np.sqrt(
                    sum(
                        (weights[r["symbol"]] * r["vol"]) ** 2
                        for r in long_side + short_side
                    )
                )
                if approx_vol > 0:
                    scale = min(1.0, TARGET_DAILY_VOL / approx_vol)
                    weights = {s: w * scale for s, w in weights.items()}

        return weights

    def _rebalance(self):
        if self.live_mode:
            raise RuntimeError("NB07 governance denial: live execution is prohibited.")
        if self.is_warming_up or self._champion_model is None:
            return

        latest = self._latest_features()
        if latest.empty:
            return

        proposed = self._portfolio_weights(latest)
        approved = self._risk.review(self, proposed)

        for symbol in self._symbols:
            self.set_holdings(symbol, float(approved.get(symbol, 0.0)))

        self._record(
            "REBALANCE",
            {
                "champion": self._champion_name,
                "proposed_positions": len(proposed),
                "approved_positions": len(approved),
                "risk_report": self._risk.last_report,
            },
        )

    def on_dividends(self, dividends):
        for symbol, dividend in dividends.items():
            if symbol in self._event_dates:
                self._event_dates[symbol]["dividend"] = self.time.date()
                self._record(
                    "DIVIDEND",
                    {
                        "symbol": str(symbol),
                        "distribution": float(dividend.distribution),
                    },
                )

    def on_splits(self, splits):
        for symbol, split in splits.items():
            if symbol in self._event_dates:
                self._event_dates[symbol]["split"] = self.time.date()
                self._record(
                    "SPLIT",
                    {
                        "symbol": str(symbol),
                        "split_factor": float(split.split_factor),
                        "type": str(split.type),
                    },
                )

    def on_order_event(self, order_event):
        if order_event.status in [
            OrderStatus.FILLED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCELED,
            OrderStatus.INVALID,
        ]:
            self._record(
                "ORDER_EVENT",
                {
                    "order_id": order_event.order_id,
                    "symbol": str(order_event.symbol),
                    "status": str(order_event.status),
                    "fill_quantity": float(order_event.fill_quantity),
                    "fill_price": float(order_event.fill_price),
                },
            )

    def on_data(self, data):
        # Explicitly keep live denial inside the event loop as a second boundary.
        if self.live_mode:
            raise RuntimeError("NB07 governance denial: live execution is prohibited.")

    def on_end_of_algorithm(self):
        bundle = {
            "notebook": "NB07",
            "bridge": "QuantConnect/LEAN",
            "status": "BACKTEST_RESEARCH_ONLY",
            "live_trading_authorized": False,
            "deployment_authorized": False,
            "champion": self._champion_name,
            "model_diagnostics": self._model_diagnostics,
            "risk_report": self._risk.last_report,
            "audit_events": self._audit,
            "audit_head": stable_hash(self._audit),
            "configuration_hash": stable_hash({
                "models": MODEL_FAMILIES,
                "features": FEATURES,
                "portfolio_method": PORTFOLIO_METHOD,
                "universe": UNIVERSE_BY_SECTOR,
            }),
        }

        try:
            self.object_store.save(
                AUDIT_OBJECT_STORE_KEY,
                json.dumps(bundle, sort_keys=True, default=str),
            )
        except Exception as exc:
            self.log(f"NB07 Object Store warning: {exc}")

        self.log(
            "NB07 COMPLETE: research-only QuantConnect backtest; "
            f"champion={self._champion_name}; live authority=DENIED"
        )
