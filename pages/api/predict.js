import path from 'path'
import fs from 'fs'

// Reject oversized bodies before we ever parse them. A valid request is well
// under 1 KB; 4 KB leaves generous headroom while blocking payload abuse.
export const config = {
  api: {
    bodyParser: { sizeLimit: '4kb' },
  },
}

// Feature order after sklearn ColumnTransformer(remainder='passthrough'):
//   f0=neighbourhood, f1=property_type, f2=bedrooms … f8=pets_allowed
let _model = null
function getModel() {
  if (!_model) {
    const p = path.join(process.cwd(), 'model', 'model_export.json')
    _model = JSON.parse(fs.readFileSync(p, 'utf8'))
  }
  return _model
}

// --- Rate limiting -----------------------------------------------------------
// In-memory sliding window, keyed by client IP.
// NOTE: this is per-instance. On serverless (Vercel), each warm instance keeps
// its own counter, so the effective global limit is (instances × RATE_LIMIT).
// For a strict global limit, back this with a shared store (Redis / Upstash).
const RATE_LIMIT = 30            // max requests
const RATE_WINDOW_MS = 60_000    // per 60s window
const _hits = new Map()          // ip -> number[] (timestamps)

function clientIp(req) {
  const xff = req.headers['x-forwarded-for']
  if (typeof xff === 'string' && xff.length) return xff.split(',')[0].trim()
  return req.socket?.remoteAddress || 'unknown'
}

function isRateLimited(ip) {
  const now = Date.now()
  const recent = (_hits.get(ip) || []).filter(t => now - t < RATE_WINDOW_MS)
  recent.push(now)
  _hits.set(ip, recent)
  // Opportunistic cleanup so the map can't grow unbounded.
  if (_hits.size > 10_000) {
    for (const [k, v] of _hits) {
      if (v.every(t => now - t >= RATE_WINDOW_MS)) _hits.delete(k)
    }
  }
  return recent.length > RATE_LIMIT
}

// --- Input validation --------------------------------------------------------
// Every field is whitelisted and range-checked. Categoricals must match a known
// category exactly (no reflection, no injection surface); numerics are coerced
// then bounds-checked; booleans accept only true/false forms.
const NUM_BOUNDS = {
  bedrooms:  [0, 10],
  bathrooms: [1, 10],
  size_sqft: [100, 10_000],
}
const BOOL_FIELDS = ['has_parking', 'has_laundry', 'furnished', 'pets_allowed']

function coerceBool(v) {
  if (v === true || v === false) return v
  if (v === 'true' || v === 1 || v === '1') return true
  if (v === 'false' || v === 0 || v === '0') return false
  return null
}

function validate(body, model) {
  if (typeof body !== 'object' || body === null || Array.isArray(body)) {
    return { error: 'Request body must be a JSON object.' }
  }
  const { categories } = model
  const out = {}

  if (typeof body.neighbourhood !== 'string' ||
      !categories.neighbourhood.includes(body.neighbourhood)) {
    return { error: 'Invalid or unknown "neighbourhood".' }
  }
  out.neighbourhood = body.neighbourhood

  if (typeof body.property_type !== 'string' ||
      !categories.property_type.includes(body.property_type)) {
    return { error: 'Invalid or unknown "property_type".' }
  }
  out.property_type = body.property_type

  for (const [field, [min, max]] of Object.entries(NUM_BOUNDS)) {
    const n = Number(body[field])
    if (!Number.isFinite(n) || n < min || n > max) {
      return { error: `"${field}" must be a number between ${min} and ${max}.` }
    }
    out[field] = n
  }

  for (const field of BOOL_FIELDS) {
    const b = coerceBool(body[field])
    if (b === null) {
      return { error: `"${field}" must be a boolean.` }
    }
    out[field] = b
  }

  return { value: out }
}

// --- Inference ---------------------------------------------------------------
function buildMap(node, out = {}) {
  out[node.nodeid] = node
  if (node.children) node.children.forEach(c => buildMap(c, out))
  return out
}

function traverse(node, map, features) {
  let n = node
  while (!('leaf' in n)) {
    const fi = parseInt(n.split.slice(1), 10)
    const v = features[fi]
    const next = (v === null || v === undefined || Number.isNaN(v))
      ? n.missing
      : v < n.split_condition ? n.yes : n.no
    n = map[next]
  }
  return n.leaf
}

function xgbPredict(input, model) {
  const { categories, trees, base_score } = model
  const features = [
    categories.neighbourhood.indexOf(input.neighbourhood),
    categories.property_type.indexOf(input.property_type),
    input.bedrooms,
    input.bathrooms,
    input.size_sqft,
    input.has_parking  ? 1 : 0,
    input.has_laundry  ? 1 : 0,
    input.furnished    ? 1 : 0,
    input.pets_allowed ? 1 : 0,
  ]
  let sum = base_score
  for (const root of trees) sum += traverse(root, buildMap(root), features)
  return Math.round(sum)
}

// --- Handler -----------------------------------------------------------------
export default function handler(req, res) {
  if (req.method === 'OPTIONS') return res.status(200).end()
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const ip = clientIp(req)
  if (isRateLimited(ip)) {
    res.setHeader('Retry-After', '60')
    return res.status(429).json({ error: 'Too many requests. Try again shortly.' })
  }

  let model
  try {
    model = getModel()
  } catch {
    return res.status(500).json({ error: 'Model unavailable.' })
  }

  const { value, error } = validate(req.body, model)
  if (error) return res.status(400).json({ error })

  try {
    const rent = xgbPredict(value, model)
    return res.status(200).json({ rent })
  } catch {
    // Never leak internal error details to the client.
    return res.status(500).json({ error: 'Prediction failed.' })
  }
}
