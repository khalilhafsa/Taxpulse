import { createContext, useContext } from 'react'

/** True on the public demo, where agents replay recorded results and risky actions are switched off. */
export const DemoContext = createContext(false)
export const useDemo = () => useContext(DemoContext)
