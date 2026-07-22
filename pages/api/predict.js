import path from 'path'
import fs from 'fs'

// Feature order after sklearn ColumnTransformer(remainder='passthrough'):
//   OrdinalEncoder outputs first: f0=neighbourhood, f1=property_type
//   then passthrough in FEATURES order: f2=bedrooms … f8=pets_allowed
const FEAT = [
  'neighbourhood', 'property_type',
  'bedrooms', 'bathrooms', 'size_sqft',
  'has_parking', 'has_laundry', 'furnished', 'pets_allowed',
]

let _model = null
function getModel() {
  if (!_model) {
    const p = path.join(process.cwd(), 'model', 'model_export.json')
    _model = JSON.parse(fs.readFileSync(p, 'utf8'))
  }
  return _model
}

/** Build a flat nodeid→node map for fast lookup during traversal. */
function buildMap(node, out = {}) {
  out[node.nodeid] = node
  if (node.children) node.children.forEach(c => buildMap(c, out))
  return out
}

/** Traverse one tree, return the leaf value. */
function traverse(node, map, features) {
  if ('leaf' in node) return node.leaf
  const fi = parseInt(node.split.slice(1), 10)
  const v  = features[fi]
  const next = (v === null || v === undefined || isNaN(v))
    ? node.missing
    : v < node.split_condition ? node.yes : node.no
  return traverse(map[next], map, features)
}

function xgbPredict(input, model) {
  const { categories, trees, base_score } = model

  // Ordinal-encode categoricals (unknown → -1, same as sklearn's unknown_value)
  const nhIdx = categories.neighbourhood.indexOf(input.neighbourhood)
  const ptIdx = categories.property_type.indexOf(input.property_type)

  const features = [
    nhIdx,                          // f0
    ptIdx,                          // f1
    Number(input.bedrooms),         // f2
    Number(input.bathrooms),        // f3
    Number(input.size_sqft),        // f4
    input.has_parking  ? 1 : 0,    // f5
    input.has_laundry  ? 1 : 0,    // f6
    input.furnished    ? 1 : 0,    // f7
    input.pets_allowed ? 1 : 0,    // f8
  ]

  let sum = base_score
  for (const root of trees) {
    const map = buildMap(root)
    sum += traverse(root, map, features)
  }
  return Math.round(sum)
}

export default function handler(req, res) {
  if (req.method === 'OPTIONS') {
    return res.status(200).end()
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }
  try {
    const model = getModel()
    const rent  = xgbPredict(req.body, model)
    res.status(200).json({ rent })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
}
