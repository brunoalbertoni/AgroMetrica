from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums import Sistema, TipoImagem
from app.routers.imagens import ImagemOut, imagem_out
from app.schemas.talhao import ClimaDiaOut, MetricaOut, OperacaoOut, SoloOut, TalhaoOut, TalhaoPagina
from app.services import talhoes as svc

router = APIRouter(tags=["talhoes"], dependencies=[Depends(get_current_user)])


@router.get("/talhoes", response_model=TalhaoPagina)
def listar(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    sort: str | None = None,
    busca: str | None = None,
    deficit_min: float | None = Query(None, ge=0, description="mm de déficit (balanço ≤ −valor)"),
    sistema: Sistema | None = None,
    db: Session = Depends(get_db),
):
    return svc.listar(db, page, size, sort, busca, deficit_min, sistema)


@router.get("/talhoes/{talhao_id}", response_model=TalhaoOut)
def detalhe(talhao_id: int, db: Session = Depends(get_db)):
    return svc.detalhe(db, talhao_id)


@router.get("/talhoes/{talhao_id}/metricas", response_model=list[MetricaOut])
def metricas(talhao_id: int, de: date | None = None, ate: date | None = None, db: Session = Depends(get_db)):
    return svc.metricas(db, talhao_id, de, ate)


@router.get("/talhoes/{talhao_id}/solo", response_model=list[SoloOut])
def solo(talhao_id: int, db: Session = Depends(get_db)):
    return svc.solo(db, talhao_id)


@router.get("/talhoes/{talhao_id}/operacoes", response_model=list[OperacaoOut])
def operacoes(talhao_id: int, db: Session = Depends(get_db)):
    return svc.operacoes(db, talhao_id)


@router.get("/talhoes/{talhao_id}/imagens", response_model=list[ImagemOut])
def imagens(talhao_id: int, tipo: TipoImagem | None = None, db: Session = Depends(get_db)):
    return [imagem_out(img) for img in svc.imagens(db, talhao_id, tipo)]


@router.get("/clima", response_model=list[ClimaDiaOut])
def clima(
    de: date | None = None,
    ate: date | None = None,
    agregacao: str = Query("dia", pattern="^dia$"),
    db: Session = Depends(get_db),
):
    return svc.clima_diario(db, de, ate)
