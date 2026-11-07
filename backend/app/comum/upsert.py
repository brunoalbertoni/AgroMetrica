from sqlalchemy.orm import Session


def upsert(db: Session, modelo, linhas: list[dict], chaves: tuple[str, ...], lote: int = 500) -> None:
    """INSERT ... ON DUPLICATE KEY UPDATE (MySQL) / ON CONFLICT DO UPDATE (SQLite).

    Atualiza só as colunas presentes nas linhas, então reenviar um arquivo não duplica registros
    e um arquivo parcial (ex.: só produtividade) não apaga o NDVI já gravado.
    """
    if not linhas:
        return
    dialeto = db.get_bind().dialect.name
    tabela = modelo.__table__
    for inicio in range(0, len(linhas), lote):
        parte = linhas[inicio : inicio + lote]
        colunas = [c for c in parte[0] if c not in chaves]
        if dialeto == "mysql":
            from sqlalchemy.dialects.mysql import insert

            stmt = insert(tabela).values(parte)
            atualizar = {c: stmt.inserted[c] for c in colunas} or {chaves[0]: stmt.inserted[chaves[0]]}
            stmt = stmt.on_duplicate_key_update(**atualizar)
        elif dialeto == "sqlite":
            from sqlalchemy.dialects.sqlite import insert

            stmt = insert(tabela).values(parte)
            atualizar = {c: stmt.excluded[c] for c in colunas}
            stmt = (
                stmt.on_conflict_do_update(index_elements=list(chaves), set_=atualizar)
                if atualizar
                else stmt.on_conflict_do_nothing(index_elements=list(chaves))
            )
        else:
            raise NotImplementedError(f"upsert não suportado para {dialeto}")
        db.execute(stmt)
    db.commit()
