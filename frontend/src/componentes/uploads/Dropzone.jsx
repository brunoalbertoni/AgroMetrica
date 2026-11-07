import { useDropzone } from 'react-dropzone'

/** Área de arrastar e soltar um arquivo. */
export default function Dropzone({ onArquivo, aceitar, texto, desabilitado = false, arquivo }) {
  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop: (aceitos) => aceitos[0] && onArquivo(aceitos[0]),
    accept: aceitar,
    multiple: false,
    disabled: desabilitado,
  })
  const rejeitado = fileRejections[0]

  return (
    <div>
      <div
        {...getRootProps()}
        className={`cursor-pointer rounded-md border-2 border-dashed px-6 py-8 text-center transition-colors ${
          isDragActive ? 'border-canopy bg-canopy-soft' : 'border-line bg-paper hover:border-canopy'
        } ${desabilitado ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        <input {...getInputProps()} />
        <p className="font-medium text-ink">{isDragActive ? 'Solte o arquivo aqui' : texto}</p>
        <p className="mt-1 text-sm text-muted">
          {arquivo ? `Selecionado: ${arquivo.name}` : 'Arraste para cá ou clique para escolher.'}
        </p>
      </div>
      {rejeitado && (
        <p className="mt-2 text-sm text-alarm">{rejeitado.file.name} não é um formato aceito aqui.</p>
      )}
    </div>
  )
}
