import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { mensagemErro } from '../api/client'
import { enviarImagem, obterImagem } from '../api/imagens'
import { listarTalhoes } from '../api/talhoes'
import { enviarPlanilha } from '../api/uploads'
import Dropzone from '../components/Dropzone'
import ImageCompare from '../components/ImageCompare'
import { Button, ErrorMessage, Field, PageHeader, Panel, inputClass } from '../components/ui'

const TIPOS_PLANILHA = [
  {
    id: 'clima',
    rotulo: 'Clima (estação Metos)',
    dica: 'Data/hora, temperatura, chuva, umidade, vento, ETP.',
  },
  { id: 'solo', rotulo: 'Solo (Cropman)', dica: 'Talhão, ponto, data da coleta, pH, MO, P, K, V%…' },
  { id: 'ndvi', rotulo: 'NDVI (OneSoil)', dica: 'Talhão, data e NDVI médio (mín. e máx. opcionais).' },
  {
    id: 'colheita',
    rotulo: 'Colheita (EKOS)',
    dica: 'Talhão, data e produtividade em kg/ha; é agregada por talhão.',
  },
]

const TIPOS_IMAGEM = [
  { id: 'FOLHA', rotulo: 'Foto de folha (RGB)' },
  { id: 'ORTOMOSAICO', rotulo: 'Ortomosaico de drone (RGB)' },
  { id: 'NDVI_GEOTIFF', rotulo: 'NDVI em GeoTIFF (OneSoil)' },
  { id: 'ARMADILHA', rotulo: 'Foto de armadilha' },
]

const ACEITA_PLANILHA = {
  'text/csv': ['.csv'],
  'text/plain': ['.csv', '.txt'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
}

function Planilhas() {
  const queryClient = useQueryClient()
  const [tipo, setTipo] = useState('clima')
  const [arquivo, setArquivo] = useState(null)
  const envio = useMutation({
    mutationFn: () => enviarPlanilha(tipo, arquivo),
    onSuccess: () => queryClient.invalidateQueries(),
  })
  const r = envio.data
  const dica = TIPOS_PLANILHA.find((t) => t.id === tipo)?.dica

  return (
    <Panel titulo="Planilhas">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          envio.mutate()
        }}
      >
        <Field label="O que é este arquivo?" dica={dica}>
          <select
            value={tipo}
            onChange={(e) => {
              setTipo(e.target.value)
              envio.reset()
            }}
            className={inputClass}
          >
            {TIPOS_PLANILHA.map((t) => (
              <option key={t.id} value={t.id}>
                {t.rotulo}
              </option>
            ))}
          </select>
        </Field>
        <Dropzone
          texto="Arraste o CSV ou XLSX"
          aceitar={ACEITA_PLANILHA}
          arquivo={arquivo}
          onArquivo={(f) => {
            setArquivo(f)
            envio.reset()
          }}
        />
        <p className="text-xs text-muted">
          Separador (; ou ,) e vírgula decimal são detectados sozinhos. Datas no formato dia/mês/ano.
        </p>
        <Button type="submit" disabled={!arquivo || envio.isPending}>
          {envio.isPending ? 'Importando…' : 'Importar planilha'}
        </Button>
      </form>

      <div className="mt-4">
        <ErrorMessage>{envio.error && mensagemErro(envio.error)}</ErrorMessage>
      </div>
      {r && (
        <div className="mt-4" aria-live="polite">
          <p className="text-sm">
            <span className="font-display text-2xl font-semibold text-canopy tabular">{r.linhas_ok}</span>{' '}
            linhas importadas
            {r.linhas_erro > 0 && (
              <>
                {', '}
                <span className="font-display text-2xl font-semibold text-alarm tabular">
                  {r.linhas_erro}
                </span>{' '}
                com erro
              </>
            )}
            .
          </p>
          {r.erros.length > 0 && (
            <div className="mt-3 max-h-64 overflow-y-auto rounded border border-line">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-paper text-muted">
                  <tr>
                    <th className="w-20 px-3 py-2 text-left font-medium">Linha</th>
                    <th className="px-3 py-2 text-left font-medium">Problema</th>
                  </tr>
                </thead>
                <tbody>
                  {r.erros.map((e) => (
                    <tr key={e.linha} className="border-t border-line">
                      <td className="px-3 py-1.5 tabular">{e.linha}</td>
                      <td className="px-3 py-1.5">{e.erro}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}

function Imagens() {
  const [talhaoId, setTalhaoId] = useState('')
  const [tipo, setTipo] = useState('FOLHA')
  const [arquivo, setArquivo] = useState(null)
  const { data: talhoes } = useQuery({
    queryKey: ['talhoes', 'todos'],
    queryFn: () => listarTalhoes({ size: 200 }),
  })
  const envio = useMutation({ mutationFn: () => enviarImagem({ arquivo, talhaoId, tipo }) })
  const imagemId = envio.data?.id
  const { data: imagem } = useQuery({
    queryKey: ['imagem', imagemId],
    queryFn: () => obterImagem(imagemId),
    enabled: Boolean(imagemId),
    refetchInterval: (q) => (['PROCESSADO', 'ERRO'].includes(q.state.data?.status) ? false : 1500),
  })

  const aceitar =
    tipo === 'NDVI_GEOTIFF'
      ? { 'image/tiff': ['.tif', '.tiff'] }
      : { 'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'] }

  return (
    <Panel titulo="Imagens">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          envio.mutate()
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Talhão">
            <select
              required
              value={talhaoId}
              onChange={(e) => setTalhaoId(e.target.value)}
              className={inputClass}
            >
              <option value="">Escolha o talhão</option>
              {talhoes?.items.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nome}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Tipo de imagem">
            <select
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value)
                setArquivo(null)
              }}
              className={inputClass}
            >
              {TIPOS_IMAGEM.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.rotulo}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Dropzone texto="Arraste a imagem" aceitar={aceitar} arquivo={arquivo} onArquivo={setArquivo} />
        <Button type="submit" disabled={!arquivo || !talhaoId || envio.isPending}>
          {envio.isPending ? 'Enviando…' : 'Enviar imagem'}
        </Button>
      </form>

      <div className="mt-4">
        <ErrorMessage>{envio.error && mensagemErro(envio.error)}</ErrorMessage>
      </div>
      {imagem && (
        <div className="mt-4 space-y-3" aria-live="polite">
          {imagem.status === 'ERRO' && (
            <ErrorMessage>
              Não foi possível processar esta imagem. Confira se o arquivo abre normalmente.
            </ErrorMessage>
          )}
          {['PENDENTE', 'PROCESSANDO'].includes(imagem.status) && (
            <p className="text-sm text-muted">Processando a imagem…</p>
          )}
          {imagem.status === 'PROCESSADO' && (
            <>
              <ImageCompare
                original={imagem.indice === 'NDVI' ? imagem.url_processada : imagem.url}
                processada={imagem.indice === 'VARI' ? imagem.url_processada : null}
                rotulo="índice RGB (VARI)"
                alt="Imagem enviada"
              />
              {imagem.indice === 'VARI' && (
                <p className="text-xs text-muted">
                  Mapa do índice RGB (VARI), calculado só com as cores visíveis da foto. Não é NDVI: vermelho
                  indica pouca vegetação verde e verde indica vegetação vigorosa.
                </p>
              )}
              {imagem.indice === 'NDVI' && (
                <p className="text-sm">
                  NDVI médio gravado nas métricas do talhão.{' '}
                  <Link to={`/talhoes/${imagem.talhao_id}`} className="text-canopy underline">
                    Ver no talhão
                  </Link>
                </p>
              )}
            </>
          )}
        </div>
      )}
    </Panel>
  )
}

export default function Upload() {
  return (
    <>
      <PageHeader
        titulo="Enviar dados"
        descricao="Importe as planilhas das máquinas e sensores ou envie imagens para processar."
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <Planilhas />
        <Imagens />
      </div>
    </>
  )
}
