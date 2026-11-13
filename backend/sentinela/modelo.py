"""Modelo carregado uma vez por processo (singleton via atributos de classe)."""
import json
from pathlib import Path
from typing import Any, ClassVar

import lightgbm as lgb
import numpy as np
import shap

from .config import settings
from .features import FEATURES, ROTULOS_PT


class Modelo:
    booster: lgb.Booster | None = None
    explainer: shap.TreeExplainer | None = None
    meta: ClassVar[dict[str, Any]] = {}

    @classmethod
    def carregar(cls, model_path: str | None = None, meta_path: str | None = None) -> bool:
        """Carrega modelo e meta; False (e modelo vazio) se os arquivos não existirem."""
        model_path = model_path or settings.model_path
        meta_path = meta_path or settings.model_meta_path
        if not (Path(model_path).exists() and Path(meta_path).exists()):
            cls.booster, cls.explainer, cls.meta = None, None, {}
            return False
        cls.booster = lgb.Booster(model_file=model_path)
        cls.explainer = shap.TreeExplainer(cls.booster)
        cls.meta = json.loads(Path(meta_path).read_text())
        return True

    @classmethod
    def carregado(cls) -> bool:
        return cls.booster is not None

    @classmethod
    def versao(cls) -> str | None:
        return cls.meta.get("versao")

    @staticmethod
    def _vetor(features: dict[str, Any]) -> np.ndarray:
        return np.array([[features[k] for k in FEATURES]], dtype=float)

    @classmethod
    def pontuar(cls, features: dict[str, Any]) -> float:
        return float(cls.booster.predict(cls._vetor(features))[0])

    @classmethod
    def explicar(cls, features: dict[str, Any]) -> list[dict[str, Any]]:
        """Top 5 features por |impacto| SHAP (log-odds; positivo aumenta o risco)."""
        sv = cls.explainer.shap_values(cls._vetor(features))
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
