"""Treino do modelo com split temporal 80/20 (`python -m sentinela.treino`)."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import grafo
from .config import settings
from .db import Conta, SessionLocal, Transacao, init_db
from .features import FEATURES, EstadoMemoria, calcular_features

LIMIARES = (0.4, 0.85)
FRACAO_TREINO = 0.8


def average_precision(y: np.ndarray, scores: np.ndarray) -> float:
    """PR-AUC: média da precisão acumulada em cada positivo, ordenando por score desc."""
    y = np.asarray(y)[np.argsort(-np.asarray(scores), kind="stable")]
    if y.sum() == 0:
        return 0.0
    precisao = np.cumsum(y) / np.arange(1, len(y) + 1)
    return float(precisao[y == 1].mean())


def metricas_grafo_treino(txs_treino: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Grafo e fraudes conhecidas só da janela de treino (evita vazamento)."""
    fraude = {t["destino"] for t in txs_treino if t["is_fraude"]}
    return grafo.calcular_metricas(grafo.construir(txs_treino), fraude)


def carregar_transacoes(sessao: Session) -> list[dict[str, Any]]:
    linhas = sessao.execute(select(Transacao.__table__).order_by(Transacao.ts, Transacao.id))
    return [dict(m) for m in linhas.mappings()]


def treinar(
    sessao: Session,
    n_estimators: int = 300,
    model_path: str | None = None,
    meta_path: str | None = None,
) -> dict[str, Any]:
    """Treina, avalia nos 20% finais, salva modelo + meta e retorna a meta."""
    model_path = model_path or settings.model_path
    meta_path = meta_path or settings.model_meta_path
    txs = carregar_transacoes(sessao)
    criada_em = dict(sessao.execute(select(Conta.id, Conta.criada_em)).all())
    corte = int(len(txs) * FRACAO_TREINO)

    estado = EstadoMemoria()
    estado.grafo_metricas = metricas_grafo_treino(txs[:corte])
    linhas = []
    for tx in txs:
        f = calcular_features(tx, estado, criada_em)
        linhas.append([f[k] for k in FEATURES])
        estado.registrar(tx)
    X = np.array(linhas, dtype=float)
    y = np.array([t["is_fraude"] for t in txs], dtype=int)
    X_tr, y_tr, X_te, y_te = X[:corte], y[:corte], X[corte:], y[corte:]

    pos = int(y_tr.sum())
    params = {
        "objective": "binary",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "scale_pos_weight": (len(y_tr) - pos) / max(pos, 1),
        "random_state": 42,
        "verbose": -1,
    }
    booster = lgb.train(params, lgb.Dataset(X_tr, y_tr, feature_name=FEATURES), num_boost_round=n_estimators)

    scores = booster.predict(X_te)
    limiares = {}
    for lim in LIMIARES:
        pred = scores >= lim
        tp = int((pred & (y_te == 1)).sum())
        limiares[str(lim)] = {
            "precisao": round(tp / max(int(pred.sum()), 1), 4),
            "recall": round(tp / max(int(y_te.sum()), 1), 4),
        }
    agora = datetime.now()
    meta = {
        "versao": f"v{agora:%Y%m%d%H%M%S}",
        "features": FEATURES,
        "metricas": {
            "pr_auc": round(average_precision(y_te, scores), 4),
            "limiares": limiares,
            "amostras_treino": len(y_tr),
            "amostras_teste": len(y_te),
            "taxa_fraude_teste": round(float(y_te.mean()), 4) if len(y_te) else 0.0,
        },
        "treinado_em": agora.isoformat(timespec="seconds"),
    }
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    # grava em .tmp e troca: quem lê vê o arquivo antigo inteiro ou o novo inteiro
    booster.save_model(f"{model_path}.tmp")
    os.replace(f"{model_path}.tmp", model_path)
    Path(f"{meta_path}.tmp").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    os.replace(f"{meta_path}.tmp", meta_path)
    return meta


if __name__ == "__main__":
    init_db()
    with SessionLocal() as s:
        print(json.dumps(treinar(s)["metricas"], indent=2))
