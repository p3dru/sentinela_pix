"""Modelo carregado uma vez por processo (singleton via atributos de classe)."""
import json
import threading
from pathlib import Path
from typing import Any, ClassVar

import lightgbm as lgb
import numpy as np
import shap

from .config import settings
from .features import FEATURES, ROTULOS_PT


class Modelo:
    # (booster, explainer, meta) trocados numa única atribuição: leitores nunca veem versões misturadas
    _atual: ClassVar[tuple[lgb.Booster, shap.TreeExplainer, dict[str, Any]] | None] = None
    _caminhos: ClassVar[tuple[str, str] | None] = None
    _mtime: ClassVar[int | None] = None
    _trava: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def carregar(cls, model_path: str | None = None, meta_path: str | None = None) -> bool:
        """Carrega modelo e meta; False (e modelo vazio) se os arquivos não existirem."""
        with cls._trava:
            return cls._carregar(model_path or settings.model_path, meta_path or settings.model_meta_path)

    @classmethod
    def _carregar(cls, model_path: str, meta_path: str) -> bool:
        cls._caminhos = (model_path, meta_path)
        if not (Path(model_path).exists() and Path(meta_path).exists()):
            cls._atual, cls._mtime = None, None
            return False
        mtime = Path(meta_path).stat().st_mtime_ns
        booster = lgb.Booster(model_file=model_path)
        cls._atual = (booster, shap.TreeExplainer(booster), json.loads(Path(meta_path).read_text()))
        cls._mtime = mtime
        return True

    @classmethod
    def atualizar(cls) -> bool:
        """Recarrega se o meta mudou em disco (ex.: novo seed); devolve se há modelo."""
        caminhos = cls._caminhos or (settings.model_path, settings.model_meta_path)
        meta = Path(caminhos[1])
        mtime = meta.stat().st_mtime_ns if meta.exists() else None
        if mtime != cls._mtime:
            with cls._trava:
                if mtime != cls._mtime:  # outra thread pode ter recarregado enquanto esperávamos
                    try:
                        cls._carregar(*caminhos)
                    except (OSError, ValueError, lgb.basic.LightGBMError) as e:
                        print(f"recarga do modelo falhou; mantendo a versão atual: {e!r}", flush=True)
        return cls.carregado()

    @classmethod
    def carregado(cls) -> bool:
        return cls._atual is not None

    @classmethod
    def meta_atual(cls) -> dict[str, Any]:
        atual = cls._atual
        return atual[2] if atual else {}

    @classmethod
    def versao(cls) -> str | None:
        return cls.meta_atual().get("versao")

    @staticmethod
    def _vetor(features: dict[str, Any]) -> np.ndarray:
        return np.array([[features[k] for k in FEATURES]], dtype=float)

    @classmethod
    def avaliar(cls, features: dict[str, Any]) -> tuple[float, list[dict[str, Any]], str]:
        """Score, motivos SHAP e versão lidos da MESMA versão do modelo."""
        booster, explainer, meta = cls._atual
        score = float(booster.predict(cls._vetor(features))[0])
        return score, cls._explicar(explainer, features), meta.get("versao") or ""

    @classmethod
    def pontuar(cls, features: dict[str, Any]) -> float:
        return float(cls._atual[0].predict(cls._vetor(features))[0])

    @classmethod
    def explicar(cls, features: dict[str, Any]) -> list[dict[str, Any]]:
        return cls._explicar(cls._atual[1], features)

    @classmethod
    def _explicar(cls, explainer: shap.TreeExplainer, features: dict[str, Any]) -> list[dict[str, Any]]:
        """Top 5 features por |impacto| SHAP (log-odds; positivo aumenta o risco)."""
        sv = explainer.shap_values(cls._vetor(features))
        if isinstance(sv, list):  # versões antigas do shap: [classe 0, classe 1]
            sv = sv[-1]
        sv = np.asarray(sv)
        impactos = sv[0, :, -1] if sv.ndim == 3 else sv[0]
        ordem = np.argsort(-np.abs(impactos))[:5]
        return [
            {
                "feature": FEATURES[i],
                "rotulo": ROTULOS_PT[FEATURES[i]],
                "valor": features[FEATURES[i]],
                "impacto": round(float(impactos[i]), 4),
            }
            for i in ordem
        ]
