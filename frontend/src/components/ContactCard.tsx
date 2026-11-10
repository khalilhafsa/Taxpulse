import { useState, type FormEvent } from 'react'
import { api, type Contact } from '../api'
import { ErrorNote, SectionTitle } from './ui'

/** Who to write to at this client; the Outreach Writer uses the salutation exactly. */
export default function ContactCard({ clientId, contact, onChange }: {
  clientId: number
  contact: Contact
  onChange: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<Contact>(contact)
  const [error, setError] = useState<string | null>(null)

  const save = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await api.saveContact(clientId, form)
      setEditing(false)
      onChange()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const field = 'mt-1 w-full rounded-md border border-rule bg-sheet px-3 shadow-sm py-1.5 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15'

  return (
    <section aria-labelledby="contact" className="mb-8">
      <SectionTitle id="contact">Contact</SectionTitle>
      {!editing ? (
        <div className="tp-chrome rounded-xl border border-rule bg-sheet shadow-sm px-4 py-3 text-sm">
          {contact.contact_name ? (
            <>
              <p className="font-medium">{contact.contact_name}</p>
              {contact.contact_title && <p className="text-slate">{contact.contact_title}</p>}
              <p className="mt-2 text-slate">Emails start with “{contact.salutation || 'Dear Sir or Madam,'}”</p>
            </>
          ) : (
            <p className="text-slate">No contact yet. Emails will start with “Dear Sir or Madam,”.</p>
          )}
          <button type="button" onClick={() => { setForm(contact); setEditing(true) }}
            className="mt-2 font-medium text-brand hover:underline">
            {contact.contact_name ? 'Edit contact' : 'Add contact'}
          </button>
        </div>
      ) : (
        <form onSubmit={save} className="space-y-3 tp-chrome rounded-xl border border-rule bg-sheet shadow-sm px-4 py-3">
          <label className="block text-sm">
            <span className="text-slate">Name</span>
            <input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
              placeholder="Jonas Becker" className={field} />
          </label>
          <label className="block text-sm">
            <span className="text-slate">Role</span>
            <input value={form.contact_title} onChange={(e) => setForm({ ...form, contact_title: e.target.value })}
              placeholder="Managing Director" className={field} />
          </label>
          <label className="block text-sm">
            <span className="text-slate">Salutation</span>
            <input value={form.salutation} onChange={(e) => setForm({ ...form, salutation: e.target.value })}
              placeholder="Dear Mr Becker," className={field} />
          </label>
          {error && <ErrorNote message={error} />}
          <div className="flex gap-3 text-sm">
            <button type="submit" className="tp-btn-primary rounded-md px-3 py-1.5 font-semibold">Save</button>
            <button type="button" onClick={() => setEditing(false)} className="font-medium text-slate">Cancel</button>
          </div>
        </form>
      )}
    </section>
  )
}
