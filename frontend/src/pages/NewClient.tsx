import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Button, ErrorNote, PageHeader } from '../components/ui'

export default function NewClient() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [mandate, setMandate] = useState('')
  const [contactName, setContactName] = useState('')
  const [contactTitle, setContactTitle] = useState('')
  const [salutation, setSalutation] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const client = await api.createClient(name, mandate, { contact_name: contactName, contact_title: contactTitle, salutation })
      if (files.length) await api.uploadDocuments(client.id, files)
      navigate(`/clients/${client.id}`)
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  const field = 'mt-1.5 w-full rounded-sm border border-ink/20 bg-sheet px-3 py-2 text-[15px] focus:border-petrol focus:outline-none focus:ring-2 focus:ring-petrol/15'

  return (
    <>
      <Link to="/clients" className="text-sm font-medium text-petrol hover:underline">Back to clients</Link>
      <div className="mt-4">
        <PageHeader title="Add a former client"
          intro="Upload the data room of a past due diligence mandate. Text-based PDFs work best; scanned images are not read yet." />
      </div>
      <form onSubmit={submit} className="max-w-xl space-y-6">
        <label className="block">
          <span className="text-sm font-medium">Company name</span>
          <input required minLength={2} value={name} onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Hartmann Logistik GmbH" className={field} />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Mandate</span>
          <input value={mandate} onChange={(e) => setMandate(e.target.value)}
            placeholder="e.g. Tax due diligence for the sale to Alpine Partners (2024)" className={field} />
        </label>
        <fieldset className="grid gap-4 sm:grid-cols-3">
          <legend className="mb-1.5 text-sm font-medium">Contact person <span className="font-normal text-slate">(optional)</span></legend>
          <input value={contactName} onChange={(e) => setContactName(e.target.value)} placeholder="Name" className={field} aria-label="Contact name" />
          <input value={contactTitle} onChange={(e) => setContactTitle(e.target.value)} placeholder="Role" className={field} aria-label="Contact role" />
          <input value={salutation} onChange={(e) => setSalutation(e.target.value)} placeholder="Dear Ms Lang," className={field} aria-label="Salutation" />
        </fieldset>
        <label className="block">
          <span className="text-sm font-medium">Data room files</span>
          <input type="file" accept="application/pdf,.pdf" multiple
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            className="mt-1.5 block w-full text-sm text-slate file:mr-4 file:rounded-md file:border-0 file:bg-petrol-soft file:px-4 file:py-2 file:text-sm file:font-semibold file:text-petrol" />
          {files.length > 0 && <p className="mt-2 text-sm text-slate">{files.length} PDF {files.length === 1 ? 'file' : 'files'} selected</p>}
        </label>
        {error && <ErrorNote message={error} />}
        <Button type="submit" disabled={busy || name.trim().length < 2}>
          {busy ? 'Saving and reading pages…' : 'Add client'}
        </Button>
      </form>
    </>
  )
}
