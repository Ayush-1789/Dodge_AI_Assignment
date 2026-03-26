/**
 * Graph layout and picking utilities for O2C staged layout
 */

// O2C entity type ordering (left to right flow)
const ENTITY_LANES = {
  Customer: 0,
  Address: 0.2,
  SalesOrder: 1,
  SalesOrderItem: 1.1,
  Delivery: 2,
  DeliveryItem: 2.1,
  BillingDocument: 3,
  BillingDocumentItem: 3.1,
  JournalEntry: 4,
  Material: 1.5,
  Plant: 2.5,
  default: 2.5
}

/**
 * Compute deterministic x-position (lane) for a node based on type
 * Returns value 0-4 for positioning left-to-right
 */
export function getNodeLane(nodeType) {
  return ENTITY_LANES[nodeType] ?? ENTITY_LANES.default
}

/**
 * Apply staged layout constraints:
 * x-position is deterministic by type (lanes)
 * y-position remains force-driven but influences force strength
 * This creates business-flow-aligned layout without randomness
 */
export function applyStagedLayoutConstraints(nodes, canvasWidth) {
  if (!nodes || !Array.isArray(nodes)) return nodes

  const laneWidth = canvasWidth / 5
  const result = nodes.map((node) => {
    const lane = getNodeLane(node.type)
    const targetX = (lane + 0.5) * laneWidth - canvasWidth / 2

    return {
      ...node,
      fx: targetX,
      fy: node.fy || undefined // Keep y free for force-driven layout
    }
  })

  return result
}

/**
 * Find all nodes within a spatial radius of a point in graph coordinates
 * Returns sorted by distance (nearest first)
 */
export function findNodesNearPoint(nodes, point, radius = 30) {
  if (!nodes || !Array.isArray(nodes)) return []

  const candidates = []
  for (const node of nodes) {
    if (typeof node.x !== 'number' || typeof node.y !== 'number') continue

    const dx = node.x - point.x
    const dy = node.y - point.y
    const dist = Math.sqrt(dx * dx + dy * dy)

    if (dist <= radius) {
      candidates.push({ node, dist })
    }
  }

  return candidates.sort((a, b) => a.dist - b.dist).map((c) => c.node)
}

/**
 * True spatial picking: find the topmost (by z-order) node at a point
 */
export function pickNodeAtPoint(nodes, point, radius = 30, hoveredNodeId = null, highlightedNodeIds = []) {
  const candidates = findNodesNearPoint(nodes, point, radius)
  if (candidates.length === 0) return null

  // Z-order priority: highlighted > hovered > normal
  for (const node of candidates) {
    if (highlightedNodeIds.includes(node.id)) return node
  }

  for (const node of candidates) {
    if (node.id === hoveredNodeId) return node
  }

  return candidates[0]
}

/**
 * Compute magnification lens bounds and zoom factor for dense areas
 * Returns { x, y, radius, zoomFactor } or null if no lens needed
 */
export function computeMagnificationLens(nodes, hoverPoint, hoverNodeId, lensConfig = {}) {
  const {
    baseRadius = 60,
    zoomFactor = 2.5,
    minNodeCountToActivate = 4
  } = lensConfig

  if (!hoverPoint || !hoverNodeId) return null

  const nearby = findNodesNearPoint(nodes, hoverPoint, baseRadius)
  if (nearby.length < minNodeCountToActivate) return null

  return {
    x: hoverPoint.x,
    y: hoverPoint.y,
    radius: baseRadius,
    zoomFactor,
    nodeCount: nearby.length
  }
}

/**
 * Render magnification lens overlay on canvas
 */
export function renderMagnificationLens(ctx, lens, canvasWidth, canvasHeight) {
  if (!lens) return

  const { x, y, radius, zoomFactor } = lens

  // Draw magnifying glass circle
  ctx.strokeStyle = 'rgba(99, 102, 241, 0.4)'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.arc(x, y, radius, 0, 2 * Math.PI)
  ctx.stroke()

  // Draw zoom indicator in corner
  ctx.fillStyle = 'rgba(99, 102, 241, 0.7)'
  ctx.font = 'bold 11px monospace'
  ctx.fillText(`×${zoomFactor.toFixed(1)}`, 12, canvasHeight - 40)
}
