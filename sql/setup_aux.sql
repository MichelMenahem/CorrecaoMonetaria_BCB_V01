-- =============================================================
-- setup_aux.sql
-- Correção Monetária BCB — objetos no schema aux
-- Seguro para reexecutar (IF NOT EXISTS / OR REPLACE)
-- =============================================================

-- Garante que o schema existe
CREATE SCHEMA IF NOT EXISTS aux;

-- -------------------------------------------------------------
-- Tabela: aux.indices_monetarios
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aux.indices_monetarios (
    indice      VARCHAR(20)   NOT NULL,
    competencia DATE          NOT NULL,   -- sempre dia 01 do mês
    taxa        NUMERIC(10,6) NOT NULL,   -- variação mensal em %
    inserido_em TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_indices_monetarios PRIMARY KEY (indice, competencia)
);

CREATE INDEX IF NOT EXISTS idx_ind_mon_consulta
    ON aux.indices_monetarios (indice, competencia);

COMMENT ON TABLE aux.indices_monetarios IS
    'Índices monetários mensais extraídos do BCB/SGS (IGP-M, IPCA, etc.)';

COMMENT ON COLUMN aux.indices_monetarios.indice IS
    'Nome do índice: IGP-M, IGP-DI, IPCA, INPC, INCC-DI, CDI, SELIC, TR, Poupanca';

COMMENT ON COLUMN aux.indices_monetarios.competencia IS
    'Primeiro dia do mês de referência (ex: 2024-01-01 = janeiro/2024)';

COMMENT ON COLUMN aux.indices_monetarios.taxa IS
    'Variação percentual mensal (ex: 0.54 significa 0,54%)';

-- -------------------------------------------------------------
-- Função: aux.fator_correcao()
-- Retorna o fator acumulado entre dois meses para um dado índice.
-- p_descarta_negativos = TRUE: meses negativos são tratados como 0%
-- -------------------------------------------------------------
CREATE OR REPLACE FUNCTION aux.fator_correcao(
    p_indice             TEXT,
    p_data_ini           DATE,
    p_data_fim           DATE,
    p_descarta_negativos BOOLEAN DEFAULT FALSE
)
RETURNS NUMERIC
LANGUAGE SQL
STABLE
AS $$
    SELECT COALESCE(
        EXP(SUM(
            LN(1.0 +
                CASE WHEN p_descarta_negativos
                     THEN GREATEST(taxa, 0.0)
                     ELSE taxa
                END / 100.0
            )
        )),
        1.0
    )
    FROM aux.indices_monetarios
    WHERE indice      = p_indice
      AND competencia >= DATE_TRUNC('month', p_data_ini)
      AND competencia <= DATE_TRUNC('month', p_data_fim);
$$;

COMMENT ON FUNCTION aux.fator_correcao(TEXT, DATE, DATE, BOOLEAN) IS
    'Fator de correção acumulado de p_data_ini até p_data_fim para o índice informado.
     Exemplo: SELECT aux.fator_correcao(''IPCA'', ''2020-01-01'', ''2024-12-01'');
     Com descarte de negativos: SELECT aux.fator_correcao(''IGP-M'', ''2020-01-01'', ''2024-12-01'', TRUE);';
