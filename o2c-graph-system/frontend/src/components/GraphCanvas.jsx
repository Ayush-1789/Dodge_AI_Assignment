import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { useGraph } from '../hooks/useGraph'
import GraphLegend from './GraphLegend'
import './GraphCanvas.css'

const LANE_INDEX_BY_TYPE = {
  Customer: 0,
  Address: 0,
  SalesOrder: 1,
  SalesOrderItem: 2,
  Material: 3,
  Delivery: 4,
  BillingDocument: 5,
  JournalEntry: 6,
  default: 3
}

const HUB_LINK_LIMIT = 24
const FOCUS_DEPTH = 2
const COLLAPSED_COLOR = '#22d3ee'

function safeId(value) {
  if (value === null || value === undefined) return null
  return String(value)
}

function getNodeRadius(node) {
  const degree = Number(node.degree || 0)
  const base = node.synthetic ? 8 : 5
  return base + Math.min(7, Math.sqrt(degree + 1) * 0.75)
}

function findNearestNode(nodes, point, maxDistance) {
  let nearest = null
  let nearestDistance = Infinity

  for (const node of nodes) {
    if (!Number.isFinite(node?.x) || !Number.isFinite(node?.y)) continue
    const dx = node.x - point.x
    const dy = node.y - point.y
    const distance = Math.sqrt(dx * dx + dy * dy)

    if (distance < nearestDistance) {
      nearest = node
      nearestDistance = distance
    }
  }

  if (!nearest) return null
  const clickableRadius = getNodeRadius(nearest) + maxDistance
  return nearestDistance <= clickableRadius ? nearest : null
}

function trimLabel(label, max = 26) {
  const text = String(label || '')
  if (text.length <= max) return text
  return `${text.slice(0, max - 1)}...`
}

function relationshipColor(relationship) {
  const rel = String(relationship || '').toUpperCase()
  if (rel.includes('HAS_ITEM')) return 'rgba(125, 211, 252, 0.6)'
  if (rel.includes('PLACED_BY') || rel.includes('INVOICES')) return 'rgba(250, 204, 21, 0.6)'
  if (rel.includes('REFERENCES')) return 'rgba(167, 139, 250, 0.6)'
  if (rel.includes('RECORDS')) return 'rgba(251, 146, 60, 0.6)'
  return 'rgba(148, 163, 184, 0.45)'
}

function buildAdjacency(links) {
  const map = new Map()
  for (const link of links) {
    if (!map.has(link.source)) map.set(link.source, new Set())
    if (!map.has(link.target)) map.set(link.target, new Set())
    map.get(link.source).add(link.target)
    map.get(link.target).add(link.source)
  }
  return map
}

function getFocusSet(adjacency, startNodeId, maxDepth = FOCUS_DEPTH) {
  if (!startNodeId || !adjacency.has(startNodeId)) return null
  const visited = new Set([startNodeId])
  const queue = [{ id: startNodeId, depth: 0 }]

  while (queue.length > 0) {
    const current = queue.shift()
    if (current.depth >= maxDepth) continue

    const neighbors = adjacency.get(current.id) || new Set()
    for (const neighbor of neighbors) {
      if (visited.has(neighbor)) continue
      visited.add(neighbor)
      queue.push({ id: neighbor, depth: current.depth + 1 })
    }
  }

  return visited
}

function normalizeGraph(rawGraph) {
  const inputNodes = Array.isArray(rawGraph?.nodes) ? rawGraph.nodes : []
  const inputLinks = Array.isArray(rawGraph?.links) ? rawGraph.links : []

  const nodeMap = new Map()
  for (const node of inputNodes) {
    const id = safeId(node.id)
    if (!id || nodeMap.has(id)) continue
    const lane = LANE_INDEX_BY_TYPE[node.type] ?? LANE_INDEX_BY_TYPE.default
    nodeMap.set(id, {
      ...node,
      id,
      label: node.label || id,
      lane,
      degree: 0,
      synthetic: false
    })
  }

  const linkMap = new Map()
  for (const link of inputLinks) {
    const source = safeId(typeof link.source === 'object' ? link.source?.id : link.source)
    const target = safeId(typeof link.target === 'object' ? link.target?.id : link.target)
    if (!source || !target || source === target) continue
    if (!nodeMap.has(source) || !nodeMap.has(target)) continue

    const relationship = link.relationship || 'RELATED_TO'
    const key = `${source}|${target}|${relationship}`
    if (!linkMap.has(key)) {
      linkMap.set(key, {
        source,
        target,
        relationship,
        key
      })
    }
  }

  for (const link of linkMap.values()) {
    const src = nodeMap.get(link.source)
    const tgt = nodeMap.get(link.target)
    if (src) src.degree += 1
    if (tgt) tgt.degree += 1
  }

  const nodes = [...nodeMap.values()]
  const links = [...linkMap.values()]
  return { nodes, links }
}

function assignTargetCoordinates(nodes, links = [], positionCache = null) {
  const neighborMap = new Map()
  for (const link of links) {
    if (!neighborMap.has(link.source)) neighborMap.set(link.source, new Set())
    if (!neighborMap.has(link.target)) neighborMap.set(link.target, new Set())
    neighborMap.get(link.source).add(link.target)
    neighborMap.get(link.target).add(link.source)
  }

  const laneGroups = new Map()
  for (const node of nodes) {
    if (!laneGroups.has(node.lane)) laneGroups.set(node.lane, [])
    laneGroups.get(node.lane).push(node)
  }

  const laneCount = Math.max(...nodes.map((n) => n.lane), LANE_INDEX_BY_TYPE.default) + 1
  const laneSpacing = 260
  const miniColumnSpacing = 34
  const rowSpacing = 42
  const miniColumns = 6
  const placedY = new Map()

  const sortedLanes = [...laneGroups.keys()].sort((a, b) => a - b)

  for (const lane of sortedLanes) {
    const laneNodes = laneGroups.get(lane)

    const getNeighborAverageY = (nodeId) => {
      const neighbors = neighborMap.get(nodeId)
      if (!neighbors || neighbors.size === 0) return null

      let sum = 0
      let count = 0
      for (const neighborId of neighbors) {
        if (!placedY.has(neighborId)) continue
        sum += placedY.get(neighborId)
        count += 1
      }

      if (count === 0) return null
      return sum / count
    }

    laneNodes.sort((a, b) => {
      const aNeighborY = getNeighborAverageY(a.id)
      const bNeighborY = getNeighborAverageY(b.id)

      if (aNeighborY !== null && bNeighborY !== null && aNeighborY !== bNeighborY) {
        return aNeighborY - bNeighborY
      }
      if (aNeighborY !== null && bNeighborY === null) return -1
      if (aNeighborY === null && bNeighborY !== null) return 1

      if (b.degree !== a.degree) return b.degree - a.degree
      return String(a.label).localeCompare(String(b.label))
    })

    const laneCenterX = (lane - (laneCount - 1) / 2) * laneSpacing
    const totalRows = Math.max(1, Math.ceil(laneNodes.length / miniColumns))

    laneNodes.forEach((node, index) => {
      const col = index % miniColumns
      const row = Math.floor(index / miniColumns)
      const localX = (col - (miniColumns - 1) / 2) * miniColumnSpacing
      const localY = (row - (totalRows - 1) / 2) * rowSpacing

      node.targetX = laneCenterX + localX
      node.targetY = localY

      const cachedPosition = positionCache?.get(node.id)
      if (cachedPosition && Number.isFinite(cachedPosition.x) && Number.isFinite(cachedPosition.y)) {
        node.x = cachedPosition.x
        node.y = cachedPosition.y
      } else if (typeof node.x !== 'number' || typeof node.y !== 'number') {
        node.x = node.targetX + (Math.random() - 0.5) * 36
        node.y = node.targetY + (Math.random() - 0.5) * 36
      }

      placedY.set(node.id, node.targetY)
    })
  }
}

function buildVisibleGraph(normalized, options) {
  const {
    focusNeighborhood,
    highlightedSet,
    fullFanoutEnabled,
    expandedHubIds,
    positionCache
  } = options

  const nodes = normalized.nodes
  const links = normalized.links
  const nodeMap = new Map(nodes.map((node) => [node.id, node]))

  const scopedNodes = focusNeighborhood
    ? nodes.filter((node) => focusNeighborhood.has(node.id))
    : nodes

  const allowedIds = new Set(scopedNodes.map((node) => node.id))
  const scopedLinks = links
    .map((link) => {
      const source = safeId(typeof link.source === 'object' ? link.source?.id : link.source)
      const target = safeId(typeof link.target === 'object' ? link.target?.id : link.target)
      if (!source || !target) return null
      return {
        ...link,
        source,
        target
      }
    })
    .filter((link) => link && allowedIds.has(link.source) && allowedIds.has(link.target))

  if (fullFanoutEnabled || focusNeighborhood) {
    const copiedNodes = scopedNodes.map((node) => ({ ...node }))
    assignTargetCoordinates(copiedNodes, scopedLinks, positionCache)
    return {
      nodes: copiedNodes,
      links: scopedLinks,
      hiddenLinkCount: 0
    }
  }

  const sortedLinks = [...scopedLinks].sort((a, b) => {
    const aImportant = highlightedSet.has(a.source) || highlightedSet.has(a.target)
    const bImportant = highlightedSet.has(b.source) || highlightedSet.has(b.target)
    if (aImportant !== bImportant) return aImportant ? -1 : 1

    const aScore = (nodeMap.get(a.source)?.degree || 0) + (nodeMap.get(a.target)?.degree || 0)
    const bScore = (nodeMap.get(b.source)?.degree || 0) + (nodeMap.get(b.target)?.degree || 0)
    return aScore - bScore
  })

  const visibleLinks = []
  const linkCountByNode = new Map()
  const hiddenByHub = new Map()

  for (const link of sortedLinks) {
    const sourceCount = linkCountByNode.get(link.source) || 0
    const targetCount = linkCountByNode.get(link.target) || 0

    const forceKeep =
      highlightedSet.has(link.source) ||
      highlightedSet.has(link.target) ||
      expandedHubIds.has(link.source) ||
      expandedHubIds.has(link.target)

    if (!forceKeep && (sourceCount >= HUB_LINK_LIMIT || targetCount >= HUB_LINK_LIMIT)) {
      const hubId = sourceCount >= targetCount ? link.source : link.target
      hiddenByHub.set(hubId, (hiddenByHub.get(hubId) || 0) + 1)
      continue
    }

    visibleLinks.push(link)
    linkCountByNode.set(link.source, sourceCount + 1)
    linkCountByNode.set(link.target, targetCount + 1)
  }

  const visibleNodes = scopedNodes.map((node) => ({ ...node }))

  for (const [hubId, hiddenCount] of hiddenByHub.entries()) {
    if (hiddenCount <= 0 || !nodeMap.has(hubId)) continue
    const hubNode = nodeMap.get(hubId)
    const collapsedId = `__collapsed__${hubId}`
    visibleNodes.push({
      id: collapsedId,
      label: `+${hiddenCount} hidden`,
      type: 'CollapsedHub',
      color: COLLAPSED_COLOR,
      lane: hubNode.lane,
      degree: hiddenCount,
      synthetic: true,
      parentHubId: hubId,
      properties: {
        hiddenCount,
        parentHubId: hubId
      }
    })

    visibleLinks.push({
      source: hubId,
      target: collapsedId,
      relationship: 'HIDDEN_RELATIONSHIPS',
      synthetic: true,
      key: `${hubId}|${collapsedId}|hidden`
    })
  }

  assignTargetCoordinates(visibleNodes, visibleLinks, positionCache)

  return {
    nodes: visibleNodes,
    links: visibleLinks,
    hiddenLinkCount: [...hiddenByHub.values()].reduce((sum, value) => sum + value, 0)
  }
}

export default function GraphCanvas({ onNodeClick, highlightedNodes = [], focusedNodes = [] }) {
  const fgRef = useRef(null)
  const visibleGraphRef = useRef({ nodes: [], links: [] })
  const positionCacheRef = useRef(new Map())
  const autoFitPendingRef = useRef(true)
  const pendingResponseFocusRef = useRef(false)

  const { graphData, loading, error } = useGraph()

  const [dimensions, setDimensions] = useState({
    width: typeof window !== 'undefined' ? Math.floor(window.innerWidth * 0.7) : 800,
    height: typeof window !== 'undefined' ? window.innerHeight - 64 : 600
  })
  const [focusNodeId, setFocusNodeId] = useState(null)
  const [focusEnabled, setFocusEnabled] = useState(false)
  const [hoveredNodeId, setHoveredNodeId] = useState(null)
  const [fullFanoutEnabled, setFullFanoutEnabled] = useState(false)
  const [expandedHubIds, setExpandedHubIds] = useState(new Set())
  const [previewNode, setPreviewNode] = useState(null)

  const highlightedSet = useMemo(() => new Set(highlightedNodes.map((id) => String(id))), [highlightedNodes])
  const focusedNodeSet = useMemo(() => new Set(focusedNodes.map((id) => String(id))), [focusedNodes])

  const normalizedGraph = useMemo(() => normalizeGraph(graphData), [graphData])
  const normalizedNodeIdSet = useMemo(
    () => new Set(normalizedGraph.nodes.map((node) => node.id)),
    [normalizedGraph.nodes]
  )

  const adjacency = useMemo(() => buildAdjacency(normalizedGraph.links), [normalizedGraph.links])

  const focusNeighborhood = useMemo(() => {
    if (!focusEnabled || !focusNodeId) return null
    return getFocusSet(adjacency, focusNodeId, FOCUS_DEPTH)
  }, [adjacency, focusEnabled, focusNodeId])

  const responseFocusSet = useMemo(() => {
    if (focusedNodeSet.size === 0) return null
    const scoped = [...focusedNodeSet].filter((id) => normalizedNodeIdSet.has(id))
    return scoped.length > 0 ? new Set(scoped) : null
  }, [focusedNodeSet, normalizedNodeIdSet])

  const effectiveFocusSet = focusNeighborhood || responseFocusSet

  const hoverNeighborhood = useMemo(() => {
    if (!hoveredNodeId || !adjacency.has(hoveredNodeId)) return null
    return new Set([hoveredNodeId, ...(adjacency.get(hoveredNodeId) || new Set())])
  }, [adjacency, hoveredNodeId])

  const visibleGraph = useMemo(() => {
    return buildVisibleGraph(normalizedGraph, {
      focusNeighborhood,
      highlightedSet,
      fullFanoutEnabled,
      expandedHubIds,
      positionCache: positionCacheRef.current
    })
  }, [normalizedGraph, focusNeighborhood, highlightedSet, fullFanoutEnabled, expandedHubIds])

  useEffect(() => {
    visibleGraphRef.current = visibleGraph
  }, [visibleGraph])

  useEffect(() => {
    const cache = positionCacheRef.current
    for (const node of visibleGraph.nodes) {
      if (Number.isFinite(node.x) && Number.isFinite(node.y)) {
        cache.set(node.id, { x: node.x, y: node.y })
      }
    }
  }, [visibleGraph])

  useEffect(() => {
    autoFitPendingRef.current = true
  }, [fullFanoutEnabled, focusEnabled, focusNodeId, expandedHubIds, normalizedGraph.nodes.length, normalizedGraph.links.length])

  const focusCameraOnNodeIds = useCallback((nodeIds, duration = 550) => {
    if (!fgRef.current || !nodeIds || nodeIds.size === 0) return false

    const targetNodes = (visibleGraphRef.current.nodes || []).filter(
      (node) => nodeIds.has(node.id) && Number.isFinite(node.x) && Number.isFinite(node.y)
    )

    if (targetNodes.length === 0) return false

    if (targetNodes.length === 1) {
      const node = targetNodes[0]
      fgRef.current.centerAt(node.x, node.y, duration)
      fgRef.current.zoom(2.4, duration)
      return true
    }

    let minX = Infinity
    let maxX = -Infinity
    let minY = Infinity
    let maxY = -Infinity

    for (const node of targetNodes) {
      minX = Math.min(minX, node.x)
      maxX = Math.max(maxX, node.x)
      minY = Math.min(minY, node.y)
      maxY = Math.max(maxY, node.y)
    }

    const centerX = (minX + maxX) / 2
    const centerY = (minY + maxY) / 2
    const width = Math.max(40, maxX - minX)
    const height = Math.max(40, maxY - minY)
    const padding = 180
    const zoomX = dimensions.width / (width + padding)
    const zoomY = dimensions.height / (height + padding)
    const nextZoom = Math.max(0.65, Math.min(2.2, Math.min(zoomX, zoomY)))

    fgRef.current.centerAt(centerX, centerY, duration)
    fgRef.current.zoom(nextZoom, duration)
    return true
  }, [dimensions.height, dimensions.width])

  const focusedNodesSignature = useMemo(
    () => [...focusedNodeSet].sort().join('|'),
    [focusedNodeSet]
  )

  useEffect(() => {
    if (!focusedNodesSignature || focusedNodeSet.size === 0) {
      pendingResponseFocusRef.current = false
      return
    }

    pendingResponseFocusRef.current = true
    autoFitPendingRef.current = false

    if (!fgRef.current) return

    const timer = setTimeout(() => {
      if (focusCameraOnNodeIds(focusedNodeSet, 650)) {
        pendingResponseFocusRef.current = false
      }
    }, 220)

    return () => clearTimeout(timer)
  }, [focusedNodesSignature, focusedNodeSet, focusCameraOnNodeIds])

  useEffect(() => {
    const handleResize = () => {
      setDimensions({
        width: Math.floor(window.innerWidth * 0.7),
        height: window.innerHeight - 64
      })
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('resize', handleResize)
    }

    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('resize', handleResize)
      }
    }
  }, [])

  useEffect(() => {
    if (!fgRef.current || visibleGraph.nodes.length === 0) return

    for (const node of visibleGraph.nodes) {
      node.fx = undefined
      node.fy = undefined
    }

    const charge = fgRef.current.d3Force('charge')
    if (charge) {
      charge.strength((node) => {
        const degree = Number(node.degree || 0)
        if (node.synthetic) return -40
        return Math.max(-240, -55 - degree * 3.2)
      })
    }

    const linkForce = fgRef.current.d3Force('link')
    if (linkForce) {
      linkForce.distance((link) => {
        const source = typeof link.source === 'object' ? link.source : null
        const target = typeof link.target === 'object' ? link.target : null
        if (!source || !target) return 70

        const laneGap = Math.abs((source.lane || 0) - (target.lane || 0))
        const base = source.synthetic || target.synthetic ? 36 : 58
        return base + laneGap * 34
      })
      linkForce.strength((link) => (link.synthetic ? 0.4 : 0.22))
    }

    const collision = fgRef.current.d3Force('collision')
    if (collision) {
      collision.radius((node) => getNodeRadius(node) + 6).strength(1)
    }

    const center = fgRef.current.d3Force('center')
    if (center) {
      center.strength(0.08)
    }

    fgRef.current.d3ReheatSimulation()
  }, [visibleGraph, dimensions.width])

  const handleEngineTick = useCallback(() => {
    const nodes = visibleGraphRef.current?.nodes || []

    for (const node of nodes) {
      if (!Number.isFinite(node.targetX) || !Number.isFinite(node.targetY)) continue
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) continue

      node.vx = (node.vx || 0) + (node.targetX - node.x) * 0.0028
      node.vy = (node.vy || 0) + (node.targetY - node.y) * 0.0022
    }
  }, [])

  const handleEngineStop = useCallback(() => {
    if (!fgRef.current) return

    if (pendingResponseFocusRef.current && focusedNodeSet.size > 0) {
      if (focusCameraOnNodeIds(focusedNodeSet, 600)) {
        pendingResponseFocusRef.current = false
        autoFitPendingRef.current = false
      }
      return
    }

    if (!autoFitPendingRef.current) return
    fgRef.current.zoomToFit(600, 110)
    autoFitPendingRef.current = false
  }, [focusCameraOnNodeIds, focusedNodeSet])

  const handleResetView = useCallback(() => {
    if (!fgRef.current) return
    setFocusEnabled(false)
    setFocusNodeId(null)
    setHoveredNodeId(null)
    setPreviewNode(null)
    setExpandedHubIds(new Set())
    autoFitPendingRef.current = true
    fgRef.current.d3ReheatSimulation()
    fgRef.current.zoomToFit(650, 120)
  }, [])

  const handleToggleFocus = useCallback(() => {
    if (!focusNodeId) return
    setFocusEnabled((previous) => !previous)
  }, [focusNodeId])

  const handleToggleDensity = useCallback(() => {
    setFullFanoutEnabled((previous) => !previous)
    setExpandedHubIds(new Set())
  }, [])

  const handleNodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const isHighlighted = highlightedSet.has(node.id)
    const isHovered = hoveredNodeId === node.id
    const inFocusNeighborhood = !effectiveFocusSet || effectiveFocusSet.has(node.id)
    const inHoverNeighborhood = !hoverNeighborhood || hoverNeighborhood.has(node.id)

    const alpha = inFocusNeighborhood && inHoverNeighborhood ? 1 : 0.15
    const radius = getNodeRadius(node)

    ctx.globalAlpha = alpha
    ctx.beginPath()
    ctx.fillStyle = node.color || '#60a5fa'
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
    ctx.fill()

    ctx.lineWidth = isHighlighted || isHovered ? 2.4 : 1
    ctx.strokeStyle = isHighlighted || isHovered ? '#f8fafc' : 'rgba(255, 255, 255, 0.35)'
    ctx.stroke()

    if (isHighlighted || isHovered) {
      ctx.shadowColor = node.color || '#60a5fa'
      ctx.shadowBlur = 18
      ctx.beginPath()
      ctx.arc(node.x, node.y, radius + 1.5, 0, 2 * Math.PI)
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)'
      ctx.stroke()
      ctx.shadowBlur = 0
    }

    const showLabel = globalScale >= 2 || isHighlighted || isHovered || node.synthetic
    if (showLabel) {
      const label = trimLabel(node.label || node.id)
      const fontSize = Math.max(10 / globalScale, 4)
      ctx.font = `${fontSize}px ui-sans-serif, system-ui, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'

      const textWidth = ctx.measureText(label).width
      const padX = 5 / globalScale
      const padY = 3 / globalScale
      const textY = node.y + radius + fontSize + 1

      ctx.fillStyle = 'rgba(2, 6, 23, 0.82)'
      ctx.fillRect(
        node.x - textWidth / 2 - padX,
        textY - fontSize / 2 - padY,
        textWidth + padX * 2,
        fontSize + padY * 2
      )

      ctx.fillStyle = 'rgba(248, 250, 252, 0.95)'
      ctx.fillText(label, node.x, textY)
    }

    ctx.globalAlpha = 1
  }, [effectiveFocusSet, highlightedSet, hoveredNodeId, hoverNeighborhood])

  const handleNodePointerAreaPaint = useCallback((node, color, ctx) => {
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(node.x, node.y, getNodeRadius(node) + 8, 0, 2 * Math.PI)
    ctx.fill()
  }, [])

  const handleLinkCanvasObject = useCallback((link, ctx) => {
    const source = link?.source
    const target = link?.target
    if (!source || !target || !Number.isFinite(source.x) || !Number.isFinite(target.x)) {
      return
    }

    const sourceId = source.id
    const targetId = target.id

    const isHighlighted = highlightedSet.has(sourceId) || highlightedSet.has(targetId)
    const isHovered = hoveredNodeId === sourceId || hoveredNodeId === targetId
    const inFocusNeighborhood = !effectiveFocusSet || (effectiveFocusSet.has(sourceId) && effectiveFocusSet.has(targetId))
    const inHoverNeighborhood = !hoverNeighborhood || (hoverNeighborhood.has(sourceId) && hoverNeighborhood.has(targetId))

    const alpha = inFocusNeighborhood && inHoverNeighborhood ? 1 : 0.1

    ctx.globalAlpha = alpha
    ctx.beginPath()
    ctx.moveTo(source.x, source.y)
    ctx.lineTo(target.x, target.y)

    if (isHighlighted || isHovered) {
      ctx.strokeStyle = 'rgba(248, 250, 252, 0.9)'
      ctx.lineWidth = 2.2
      ctx.shadowColor = 'rgba(148, 163, 184, 0.9)'
      ctx.shadowBlur = 10
    } else {
      ctx.strokeStyle = relationshipColor(link.relationship)
      ctx.lineWidth = link.synthetic ? 1.5 : 1.1
      ctx.shadowBlur = 0
    }

    ctx.stroke()
    ctx.globalAlpha = 1
    ctx.shadowBlur = 0
  }, [effectiveFocusSet, highlightedSet, hoveredNodeId, hoverNeighborhood])

  const handleNodeClick = useCallback((node) => {
    if (!node) return

    if (node.synthetic && node.parentHubId) {
      setExpandedHubIds((previous) => {
        const next = new Set(previous)
        next.add(node.parentHubId)
        return next
      })
      return
    }

    setFocusNodeId(node.id)
    setPreviewNode(node)
    onNodeClick?.(node.id)

    if (fgRef.current && Number.isFinite(node.x) && Number.isFinite(node.y)) {
      fgRef.current.centerAt(node.x, node.y, 400)
      fgRef.current.zoom(2.2, 450)
    }
  }, [onNodeClick])

  const handleGraphAreaClick = useCallback((event) => {
    if (!fgRef.current || !event) return

    const targetElement = event.target
    if (
      targetElement?.closest?.('.graph-controls') ||
      targetElement?.closest?.('.graph-legend') ||
      targetElement?.closest?.('.graph-stats')
    ) {
      return
    }

    const rect = event.currentTarget?.getBoundingClientRect?.()
    const hasOffset = Number.isFinite(event.offsetX) && Number.isFinite(event.offsetY)
    const canvasX = hasOffset
      ? event.offsetX
      : Number.isFinite(event.clientX) && rect
        ? event.clientX - rect.left
        : null
    const canvasY = hasOffset
      ? event.offsetY
      : Number.isFinite(event.clientY) && rect
        ? event.clientY - rect.top
        : null

    if (!Number.isFinite(canvasX) || !Number.isFinite(canvasY)) return

    const graphPoint = fgRef.current.screen2GraphCoords(canvasX, canvasY)
    const zoom = fgRef.current.zoom?.() || 1
    const proximity = Math.max(6, 10 / zoom)
    const nearestNode = findNearestNode(visibleGraphRef.current.nodes || [], graphPoint, proximity)

    if (nearestNode) {
      handleNodeClick(nearestNode)
    }
  }, [handleNodeClick])

  if (error) {
    return (
      <div className="graph-error">
        <p>Error loading graph:</p>
        <p style={{ fontSize: '12px', opacity: 0.6 }}>{error}</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="graph-loading">
        <div className="loading-spinner"></div>
        <p>Loading graph...</p>
      </div>
    )
  }

  return (
    <div className="graph-canvas-wrapper" onClick={handleGraphAreaClick}>
      <div className="graph-controls">
        <button type="button" onClick={handleResetView}>Reset View</button>
        <button type="button" onClick={handleToggleDensity}>
          {fullFanoutEnabled ? 'Balanced View' : 'Full Graph'}
        </button>
        <button type="button" onClick={handleToggleFocus} disabled={!focusNodeId}>
          {focusEnabled ? 'Exit Focus' : 'Focus 2-Hop'}
        </button>
      </div>

      <ForceGraph2D
        ref={fgRef}
        graphData={visibleGraph}
        enableNodeDrag={false}
        nodeCanvasObject={handleNodeCanvasObject}
        nodePointerAreaPaint={handleNodePointerAreaPaint}
        linkCanvasObject={handleLinkCanvasObject}
        linkCanvasObjectMode={() => 'after'}
        linkDirectionalArrowLength={2.8}
        linkDirectionalArrowRelPos={1}
        linkDirectionalParticles={0}
        onNodeClick={handleNodeClick}
        onBackgroundClick={handleGraphAreaClick}
        onNodeHover={(node) => {
          const nextId = node?.id || null
          setHoveredNodeId((prev) => (prev === nextId ? prev : nextId))
        }}
        onEngineTick={handleEngineTick}
        onEngineStop={handleEngineStop}
        cooldownTicks={360}
        cooldownTime={12000}
        warmupTicks={40}
        backgroundColor="transparent"
        width={dimensions.width}
        height={dimensions.height}
        minZoom={0.2}
        maxZoom={8}
      />

      <GraphLegend />

      {previewNode && (
        <div className="graph-node-preview">
          <div className="graph-node-preview-header">
            <div>
              <div className="graph-node-preview-type">{previewNode.type || 'Node'}</div>
              <div className="graph-node-preview-id">{previewNode.id}</div>
            </div>
            <button
              type="button"
              className="graph-node-preview-close"
              onClick={() => setPreviewNode(null)}
            >
              Close
            </button>
          </div>

          <div className="graph-node-preview-label">{previewNode.label || previewNode.id}</div>

          <div className="graph-node-preview-properties">
            {Object.entries(previewNode.properties || {})
              .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
              .slice(0, 8)
              .map(([key, value]) => (
                <div key={key} className="graph-node-preview-row">
                  <span>{key}</span>
                  <span>{String(value)}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {visibleGraph.nodes.length > 0 && (
        <div className="graph-stats">
          <span>{visibleGraph.nodes.length} nodes</span>
          <span>•</span>
          <span>{visibleGraph.links.length} relationships</span>
          {visibleGraph.hiddenLinkCount > 0 && (
            <>
              <span>•</span>
              <span>{visibleGraph.hiddenLinkCount} hidden in balanced view</span>
            </>
          )}
          {focusEnabled && focusNodeId && (
            <>
              <span>•</span>
              <span>focus: {focusNodeId}</span>
            </>
          )}
          {!focusEnabled && responseFocusSet && responseFocusSet.size > 0 && (
            <>
              <span>•</span>
              <span>response focus: {responseFocusSet.size} nodes</span>
            </>
          )}
        </div>
      )}
    </div>
  )
}

