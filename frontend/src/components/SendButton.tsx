import { useEffect, useRef, useState } from 'react'

/** The "Send to TaxPulse" bookmark. It runs on the BMF feed page after the advisor passed the security
 *  check, reads the feed that is open in the tab and posts it to the local TaxPulse API. */
export function bookmarklet(api: string, feed: string) {
  const code = `(async()=>{const T=${JSON.stringify(api)},F=${JSON.stringify(feed)};
const say=(m,ok)=>{if(!(document instanceof HTMLDocument)){alert(m);return}let d=document.getElementById('tp-toast');if(!d){d=document.createElement('div');d.id='tp-toast';document.body.appendChild(d)}d.setAttribute('style','position:fixed;z-index:2147483647;right:20px;bottom:20px;max-width:380px;padding:14px 16px;border-radius:10px;font:14px/1.45 system-ui,sans-serif;color:#fff;box-shadow:0 6px 24px rgba(0,0,0,.25);background:'+(ok?'#0f5c63':'#a8322d'));d.textContent=m;clearTimeout(window.__tpT);window.__tpT=setTimeout(()=>d.remove(),10000)};
if(!/(^|\\.)bundesfinanzministerium\\.de$/.test(location.hostname)){say('TaxPulse: this is not the BMF website. Open the BMF feed from the TaxPulse notification, then click again.');return}
say('TaxPulse: sending the BMF feed…',true);
const isRss=s=>/<rss[\\s>]|<feed[\\s>]|&lt;rss[\\s&]/i.test(s);let x='';try{x=await (await fetch(F,{credentials:'include'})).text()}catch(e){}
if(!isRss(x)){const v=document.querySelector('[id="webkit-xml-viewer-source-xml"]');const t=(document.body||document.documentElement).textContent||'';x=v&&v.firstElementChild?new XMLSerializer().serializeToString(v.firstElementChild):isRss(t)?t:''}
if(!isRss(x)){say('TaxPulse: this is a BMF web page, not the list of publications. Opening the list now: when it appears, click Send to TaxPulse again.',true);setTimeout(()=>{location.href=F},2500);return}
let r,j;try{r=await fetch(T,{method:'POST',headers:{'Content-Type':'text/plain'},body:JSON.stringify({url:location.href,xml:x})});j=await r.json()}catch(e){say('TaxPulse could not be reached. Check that TaxPulse is running (start.bat) and that this site may access apps on this device (icon left of the address bar), then click again.');return}
if(!r.ok){say('TaxPulse: '+(j.detail||'the feed was not accepted.'));return}
say(j.new?'TaxPulse: '+j.new+' new publication'+(j.new>1?'s':'')+' received. '+(j.agents_started?'The agents are analysing them; the bell will tell you what they find.':'Open TaxPulse to analyse them.'):'TaxPulse: nothing new, all '+j.found+' publications are already in TaxPulse.',true)})();`
  return 'javascript:' + encodeURIComponent(code.replace(/\n/g, ''))
}

const API = 'http://localhost:8000/api/updates/receive-feed'

export default function SendButtonSetup({ feedUrl }: { feedUrl: string }) {
  const code = bookmarklet(API, feedUrl)
  const link = useRef<HTMLAnchorElement>(null)
  const [copied, setCopied] = useState(false)
  // React refuses javascript: links in JSX, so the bookmark address is set directly on the element.
  useEffect(() => {
    link.current?.setAttribute('href', code)
    if (window.location.hash === '#send-button') document.getElementById('send-button')?.scrollIntoView({ block: 'start' })
  }, [code])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard blocked: dragging still works */ }
  }

  return (
    <section aria-labelledby="sendbutton" className="max-w-xl border-t border-rule pt-8">
      <h2 id="sendbutton" className="font-serif text-lg font-semibold">The “Send to TaxPulse” button</h2>
      <p className="mt-1 text-sm leading-relaxed text-slate">
        The BMF website lets people in but asks software to pass a security check. With this button you pass the
        check yourself, and one click sends the feed to TaxPulse. The Federal Fiscal Court (BFH) needs no button:
        TaxPulse reads it on its own.
      </p>
      <ol className="mt-4 space-y-4 text-sm">
        <li className="flex gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-petrol-soft text-xs font-semibold text-petrol">1</span>
          <div>
            <p>Show your bookmarks bar (<kbd className="rounded border border-rule px-1">Ctrl</kbd>+<kbd className="rounded border border-rule px-1">Shift</kbd>+<kbd className="rounded border border-rule px-1">B</kbd>), then drag this button onto it. Once is enough.</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <a ref={link} onClick={(e) => e.preventDefault()} draggable
                className="inline-flex cursor-grab items-center gap-2 rounded-md border-2 border-dashed border-petrol bg-petrol-soft px-3 py-1.5 font-semibold text-petrol active:cursor-grabbing"
                title="Drag me to your bookmarks bar">
                <svg viewBox="0 0 32 32" className="h-4 w-4" aria-hidden><rect width="32" height="32" rx="7" fill="#0F5C63" /><path d="M5 17h6l3-7 4 13 3-6h6" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
                Send to TaxPulse
              </a>
              <button type="button" onClick={copy} className="text-xs font-medium text-petrol hover:underline">
                {copied ? 'Copied' : 'Dragging does not work? Copy the code'}
              </button>
            </div>
            {copied && (
              <p className="mt-1 text-xs text-slate">Right-click the bookmarks bar, choose “Add page”, name it Send to TaxPulse and paste the code as the URL.</p>
            )}
          </div>
        </li>
        <li className="flex gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-petrol-soft text-xs font-semibold text-petrol">2</span>
          <p>
            When the bell asks for it, <a href={feedUrl} target="_blank" rel="noopener noreferrer" className="font-medium text-petrol hover:underline">open the BMF feed</a> and
            pass the security check. Wait until you see the list of publications.
          </p>
        </li>
        <li className="flex gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-petrol-soft text-xs font-semibold text-petrol">3</span>
          <p>
            Click <strong>Send to TaxPulse</strong> in your bookmarks bar. A message confirms what arrived and the agents start.
            The first time, your browser may ask whether the BMF page may reach apps on this computer: choose Allow.
            TaxPulse must be running.
          </p>
        </li>
      </ol>
    </section>
  )
}
