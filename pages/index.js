import Head from 'next/head'
import { useState } from 'react'

const NEIGHBOURHOODS = [
  'Annex', 'Beaches', 'Bloordale', 'Cabbagetown', 'Danforth',
  'Distillery District', 'Downtown Core', 'Etobicoke', 'Financial District',
  'Forest Hill', 'Greektown', 'Harbourfront', 'High Park', 'Junction',
  'Kensington Market', 'King West', 'Leslieville', 'Liberty Village',
  'Little Italy', 'Midtown', 'North York', 'Parkdale', 'Queen West',
  'Riverside', 'Roncesvalles', 'Rosedale', 'Scarborough', 'St. Lawrence Market',
  'Swansea', 'Yorkville',
]

const PROPERTY_TYPES = [
  'Apartment', 'Condo', 'Basement Apartment', 'House',
  'Townhouse', 'Bachelor/Studio', 'Semi-Detached',
]

const HOOD_MEDIANS = [
  ['Yorkville', 3100],
  ['Downtown Core', 2600],
  ['Liberty Village', 2450],
  ['Annex', 2300],
  ['North York', 1900],
  ['Scarborough', 1550],
]

function Toggle({ label, icon, checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border-2 text-sm font-medium transition-all ${
        checked
          ? 'border-blue-500 bg-blue-50 text-blue-700'
          : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
      }`}
    >
      <span>{icon}</span>{label}
    </button>
  )
}

function SliderField({ label, value, min, max, step, onChange, format, ticks }) {
  return (
    <div>
      <div className="flex justify-between items-baseline mb-1.5">
        <label className="text-sm font-semibold text-slate-700">{label}</label>
        <span className="text-sm font-bold text-blue-600">{format(value)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full"
      />
      {ticks && (
        <div className="flex justify-between text-xs text-slate-400 mt-1">
          {ticks.map(t => <span key={t}>{t}</span>)}
        </div>
      )}
    </div>
  )
}

export default function Home() {
  const [form, setForm] = useState({
    neighbourhood: 'Downtown Core',
    property_type: 'Apartment',
    bedrooms: 1,
    bathrooms: 1,
    size_sqft: 600,
    has_parking: false,
    has_laundry: false,
    furnished: false,
    pets_allowed: false,
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const set = key => val => setForm(f => ({ ...f, [key]: val }))

  async function predict() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setResult(data.rent)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const bedLabel = form.bedrooms === 0 ? 'Bachelor / Studio' : `${form.bedrooms} Bedroom${form.bedrooms > 1 ? 's' : ''}`

  return (
    <>
      <Head>
        <title>Toronto Rental Predictor</title>
        <meta name="description" content="ML-powered rent estimates trained on real Kijiji listings" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="min-h-screen bg-slate-50 font-sans">

        {/* Header */}
        <header className="bg-gradient-to-br from-blue-950 to-blue-800 text-white">
          <div className="max-w-5xl mx-auto px-4 py-10">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-3xl">🏙️</span>
              <h1 className="text-2xl font-bold tracking-tight">Toronto Rental Predictor</h1>
            </div>
            <p className="text-blue-200 text-sm max-w-lg">
              XGBoost model trained on <strong className="text-white">440 real Kijiji listings</strong>.
              Enter your unit details for an instant rent estimate.
            </p>
            <div className="flex gap-4 mt-4 text-xs text-blue-300">
              <span>✓ CV R² = 0.97</span>
              <span>✓ MAE ≈ $42 / month</span>
              <span>✓ 30 Toronto neighbourhoods</span>
            </div>
          </div>
        </header>

        {/* Body */}
        <main className="max-w-5xl mx-auto px-4 py-8 grid md:grid-cols-5 gap-6">

          {/* ── Form (3 cols) ── */}
          <div className="md:col-span-3 bg-white rounded-2xl shadow-sm border border-slate-100 p-6 space-y-5">

            {/* Neighbourhood + type */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Neighbourhood</label>
                <select
                  value={form.neighbourhood}
                  onChange={e => set('neighbourhood')(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  {NEIGHBOURHOODS.map(n => <option key={n}>{n}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Property Type</label>
                <select
                  value={form.property_type}
                  onChange={e => set('property_type')(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  {PROPERTY_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
            </div>

            <hr className="border-slate-100" />

            {/* Sliders */}
            <SliderField
              label="Bedrooms" value={form.bedrooms} min={0} max={4} step={1}
              onChange={set('bedrooms')} format={v => v === 0 ? 'Bachelor / Studio' : v}
              ticks={['Studio', '1', '2', '3', '4']}
            />
            <SliderField
              label="Bathrooms" value={form.bathrooms} min={1} max={3} step={0.5}
              onChange={set('bathrooms')} format={v => v}
            />
            <SliderField
              label="Size" value={form.size_sqft} min={200} max={3000} step={50}
              onChange={set('size_sqft')} format={v => `${v.toLocaleString()} ft²`}
              ticks={['200', '1,000', '2,000', '3,000 ft²']}
            />

            <hr className="border-slate-100" />

            {/* Amenity toggles */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Amenities</label>
              <div className="flex flex-wrap gap-2">
                <Toggle label="Parking"   icon="🚗" checked={form.has_parking}  onChange={set('has_parking')} />
                <Toggle label="Laundry"   icon="🧺" checked={form.has_laundry}  onChange={set('has_laundry')} />
                <Toggle label="Furnished" icon="🛋️" checked={form.furnished}    onChange={set('furnished')} />
                <Toggle label="Pets OK"   icon="🐾" checked={form.pets_allowed} onChange={set('pets_allowed')} />
              </div>
            </div>

            <button
              onClick={predict}
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
            >
              {loading ? 'Predicting…' : 'Predict Monthly Rent →'}
            </button>
          </div>

          {/* ── Result panel (2 cols) ── */}
          <div className="md:col-span-2 flex flex-col gap-4">

            {/* Prediction card */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 flex-1">
              {result ? (
                <div className="text-center h-full flex flex-col justify-center">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Estimated rent</p>
                  <p className="text-5xl font-extrabold text-blue-700 tabular-nums">
                    ${result.toLocaleString()}
                  </p>
                  <p className="text-slate-400 text-sm mt-1">CAD / month</p>
                  <div className="mt-5 text-left border-t border-slate-100 pt-4 space-y-1.5 text-sm text-slate-600">
                    <div className="flex justify-between"><span className="text-slate-400">Unit</span><span>{bedLabel} {form.property_type}</span></div>
                    <div className="flex justify-between"><span className="text-slate-400">Location</span><span>{form.neighbourhood}</span></div>
                    <div className="flex justify-between"><span className="text-slate-400">Size</span><span>{form.size_sqft.toLocaleString()} ft²</span></div>
                  </div>
                </div>
              ) : (
                <div className="text-center h-full flex flex-col justify-center py-8">
                  <span className="text-5xl mb-3 block">🏠</span>
                  <p className="text-slate-400 text-sm">
                    Fill in your unit details<br />and click predict.
                  </p>
                </div>
              )}
              {error && (
                <div className="mt-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-600">{error}</div>
              )}
            </div>

            {/* Neighbourhood reference */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Neighbourhood medians (1BR)</p>
              {HOOD_MEDIANS.map(([hood, price]) => (
                <div key={hood} className="flex items-center gap-2 mb-2 last:mb-0">
                  <span className="text-xs text-slate-500 w-28 shrink-0">{hood}</span>
                  <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-blue-400 h-full rounded-full transition-all"
                      style={{ width: `${(price / 3500) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-semibold text-slate-600 w-14 text-right">${price.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t border-slate-200 bg-white mt-4">
          <div className="max-w-5xl mx-auto px-4 py-5 flex flex-wrap justify-between items-center gap-3 text-xs text-slate-400">
            <span>Trained on 440 real Kijiji listings · XGBoost · SHAP interpretability</span>
            <a
              href="https://github.com/amahmood-sys/fantastic-octo-memory"
              target="_blank" rel="noopener noreferrer"
              className="text-blue-500 hover:underline"
            >
              View source on GitHub →
            </a>
          </div>
        </footer>
      </div>
    </>
  )
}
