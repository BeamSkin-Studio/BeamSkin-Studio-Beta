local M = {}

local defaultFileName = "beamSkinStudio_vehicle_parts"
local statusEvent = "BeamSkinStudioPartsExported"
local toDegrees = 180 / math.pi

local function report(ok, message)
  guihooks.trigger(statusEvent, {ok = ok, message = message})
end

local function finite(value)
  value = tonumber(value)
  if value == nil or value ~= value or value == math.huge or value == -math.huge then
    return 0
  end
  return value
end

local function readVec(value)
  if type(value) ~= "table" and type(value) ~= "userdata" then return nil end
  local ok, x, y, z = pcall(function() return value.x, value.y, value.z end)
  if ok and x ~= nil then return {finite(x), finite(y), finite(z)} end
  ok, x, y, z = pcall(function() return value[1], value[2], value[3] end)
  if ok and x ~= nil then return {finite(x), finite(y), finite(z)} end
  return nil
end

local function readDegrees(value)
  local v = readVec(value)
  if not v then return nil end
  return {v[1] * toDegrees, v[2] * toDegrees, v[3] * toDegrees}
end

local function nodePosition(nodes, id)
  if type(nodes) ~= "table" or type(id) ~= "number" or id < 0 then return nil end
  local node = nodes[id]
  if type(node) ~= "table" then return nil end
  return readVec(node.pos)
end

local function splitPath(path)
  local segments = {}
  for segment in tostring(path):gmatch("[^/]+") do
    segments[#segments + 1] = segment
  end
  return segments
end

local function countKeys(map)
  local n = 0
  if type(map) == "table" then
    for _ in pairs(map) do n = n + 1 end
  end
  return n
end

local function stringMap(map)
  local out, n = {}, 0
  if type(map) == "table" then
    for key, value in pairs(map) do
      if type(key) == "string" and type(value) == "string" and value ~= "" then
        out[key:gsub("^/+", ""):gsub("/+$", "")] = value
        n = n + 1
      end
    end
  end
  return out, n
end

local function addMeshes(target, rows)
  if type(rows) ~= "table" then return end
  for _, row in pairs(rows) do
    if type(row) == "table" and row.disable ~= true and type(row.mesh) == "string" and row.mesh ~= "" then
      target[row.mesh] = true
    end
  end
end

local function sortedNames(meshes)
  local names = {}
  for name in pairs(meshes) do
    names[#names + 1] = name
  end
  table.sort(names)
  return names
end

local function decodeConfigText(text)
  if type(text) ~= "string" or text == "" then return nil end
  if text:sub(1, 1) == "{" then
    local ok, data = pcall(jsonDecode, text)
    if ok and type(data) == "table" then return data end
  end
  if text:lower():match("%.pc$") then
    local ok, data = pcall(jsonReadFile, text)
    if ok and type(data) == "table" then return data end
  end
  local ok, data = pcall(function() return deserialize(text) end)
  if ok and type(data) == "table" then return data end
  return nil
end

local function playerPartConfigText()
  local ok, text = pcall(function()
    local veh = be:getPlayerVehicle(0)
    return veh and veh.partConfig
  end)
  if ok and type(text) == "string" then return text end
  return nil
end

local function configCandidates(bundle, vdata)
  local list = {}
  local function add(name, parts, config)
    list[#list + 1] = {name = name, parts = parts, config = config}
  end
  add("bundle.chosenParts", bundle.chosenParts)
  add("vdata.chosenParts", vdata.chosenParts)
  if type(bundle.config) == "table" then add("bundle.config", bundle.config.parts, bundle.config) end
  if type(vdata.config) == "table" then add("vdata.config", vdata.config.parts, vdata.config) end
  local partmgmt = extensions and extensions.core_vehicle_partmgmt
  if partmgmt and type(partmgmt.getConfig) == "function" then
    local ok, config = pcall(partmgmt.getConfig)
    if ok and type(config) == "table" then add("partmgmt.getConfig", config.parts, config) end
  end
  local decoded = decodeConfigText(playerPartConfigText())
  if decoded then add("vehicle.partConfig", decoded.parts, decoded) end
  return list
end

local function slotsOf(part)
  local out = {}
  local function collect(rows)
    if type(rows) ~= "table" then return end
    for _, slot in pairs(rows) do
      if type(slot) == "table" then
        local name = slot.name or slot.id or slot.type
        if type(name) == "string" then
          local allowed = {}
          local allow = slot.allowTypes or slot.allowedTypes or slot.type
          if type(allow) == "string" then
            allowed[allow] = true
          elseif type(allow) == "table" then
            for _, t in pairs(allow) do
              if type(t) == "string" then allowed[t] = true end
            end
          end
          out[#out + 1] = {name = name, allowed = allowed}
        end
      end
    end
  end
  collect(part.slots2)
  collect(part.slots)
  return out
end

local function deriveFromRows(rows, chosen)
  local added = 0
  if type(rows) ~= "table" then return added end
  for _, row in pairs(rows) do
    if type(row) == "table" and row.disable ~= true
        and type(row.partPath) == "string" and type(row.partOrigin) == "string" and row.partOrigin ~= "" then
      local segments = splitPath(row.partPath)
      if #segments >= 2 then
        table.remove(segments)
        local slotPath = table.concat(segments, "/")
        if chosen[slotPath] == nil then
          chosen[slotPath] = row.partOrigin
          added = added + 1
        end
      end
    end
  end
  return added
end

local function inferIntermediate(parts, mainName, chosen)
  local assigned = {}
  for _, name in pairs(chosen) do assigned[name] = true end
  if mainName ~= "" then assigned[mainName] = true end
  local needed = {}
  for path in pairs(chosen) do
    local segments = splitPath(path)
    for i = 1, #segments - 1 do
      local prefix = table.concat(segments, "/", 1, i)
      if chosen[prefix] == nil then needed[prefix] = i end
    end
  end
  local ordered = {}
  for prefix, depth in pairs(needed) do
    ordered[#ordered + 1] = {prefix, depth}
  end
  table.sort(ordered, function(a, b)
    if a[2] ~= b[2] then return a[2] < b[2] end
    return a[1] < b[1]
  end)
  local added = 0
  for _, item in ipairs(ordered) do
    local segments = splitPath(item[1])
    local slotName = segments[#segments]
    local parentName
    if #segments == 1 then
      parentName = mainName
    else
      parentName = chosen[table.concat(segments, "/", 1, #segments - 1)]
    end
    local allowed
    local parent = parentName and parts[parentName]
    if type(parent) == "table" then
      for _, slot in ipairs(slotsOf(parent)) do
        if slot.name == slotName then
          allowed = slot.allowed
          break
        end
      end
    end
    local candidates = {}
    for name, part in pairs(parts) do
      if not assigned[name] and type(part) == "table" and type(part.slotType) == "string" then
        if (allowed and allowed[part.slotType]) or part.slotType == slotName then
          candidates[#candidates + 1] = name
        end
      end
    end
    if #candidates == 1 then
      chosen[item[1]] = candidates[1]
      assigned[candidates[1]] = true
      added = added + 1
    end
  end
  return added
end

local function plainVars(vars)
  local out = {}
  if type(vars) == "table" then
    for key, value in pairs(vars) do
      local kind = type(value)
      if type(key) == "string" and (kind == "number" or kind == "string" or kind == "boolean") then
        out[key] = kind == "number" and finite(value) or value
      end
    end
  end
  return out
end

local function flexbodyRows(rows)
  local out = {}
  if type(rows) ~= "table" then return out end
  for _, row in pairs(rows) do
    if type(row) == "table" and row.disable ~= true and type(row.mesh) == "string" and row.mesh ~= "" then
      out[#out + 1] = {
        mesh = row.mesh,
        pos = readVec(row.pos) or {0, 0, 0},
        rot = readVec(row.rot) or {0, 0, 0},
        scale = readVec(row.scale),
        partOrigin = row.partOrigin,
        partPath = row.partPath
      }
    end
  end
  return out
end

local function propRows(rows, nodes)
  local out = {}
  if type(rows) ~= "table" then return out end
  for _, row in pairs(rows) do
    if type(row) == "table" and row.disable ~= true and type(row.mesh) == "string" and row.mesh ~= "" then
      out[#out + 1] = {
        mesh = row.mesh,
        func = row.func,
        idRef = row.idRef,
        idX = row.idX,
        idY = row.idY,
        refPos = nodePosition(nodes, row.idRef),
        xPos = nodePosition(nodes, row.idX),
        yPos = nodePosition(nodes, row.idY),
        baseTranslation = readVec(row.baseTranslation),
        baseRotation = readDegrees(row.baseRotation),
        baseTranslationGlobal = readVec(row.baseTranslationGlobal),
        baseRotationGlobal = readDegrees(row.baseRotationGlobal),
        partOrigin = row.partOrigin,
        partPath = row.partPath
      }
    end
  end
  return out
end

function M.exportCurrentVehicle(fileName)
  local manager = extensions.core_vehicle_manager
  local bundle = manager and manager.getPlayerVehicleData()
  local vdata = bundle and bundle.vdata
  if type(vdata) ~= "table" then
    report(false, "No active vehicle data is available.")
    return false
  end

  if type(fileName) ~= "string" then
    fileName = defaultFileName
  end
  fileName = fileName:match("^%s*(.-)%s*$")
  if fileName:lower():sub(-5) == ".json" then
    fileName = fileName:sub(1, -6)
  end
  if #fileName == 0 or #fileName > 100 or not fileName:match("^[%w_ %-]+$") then
    report(false, "Enter a filename of 1-100 letters, numbers, spaces, underscores, or hyphens.")
    return false
  end

  local model = type(vdata.model) == "string" and vdata.model or ""
  if model == "" or not model:match("^[%w_%-]+$") then
    report(false, "The active vehicle has no valid vehicle ID for the export folder.")
    return false
  end
  local exportDirectory = "settings/beamskin_studio/" .. model
  local exportPath = exportDirectory .. "/" .. fileName .. ".json"
  local directoryOk, directoryResult = pcall(function()
    return FS:directoryCreate(exportDirectory)
  end)
  if not directoryOk or directoryResult == false then
    report(false, "Could not create " .. exportDirectory .. ": " .. tostring(directoryResult))
    return false
  end

  local meshes = {}
  addMeshes(meshes, vdata.flexbodies)
  addMeshes(meshes, vdata.props)
  local parts = {}
  local activeCount = 0
  if type(vdata.activeParts) == "table" then
    for partName, part in pairs(vdata.activeParts) do
      if type(partName) == "string" and type(part) == "table" then
        activeCount = activeCount + 1
        local partMeshes = {}
        addMeshes(partMeshes, part.flexbodies)
        addMeshes(partMeshes, part.props)
        parts[#parts + 1] = {
          name = partName,
          slotType = type(part.slotType) == "string" and part.slotType or nil,
          meshNames = sortedNames(partMeshes)
        }
        for meshName in pairs(partMeshes) do
          meshes[meshName] = true
        end
      end
    end
  end
  table.sort(parts, function(a, b) return a.name < b.name end)
  local meshNames = sortedNames(meshes)
  if #meshNames == 0 then
    report(false, "The active vehicle has no exported flexbody or prop mesh names.")
    return false
  end

  local mainPartName = type(bundle.mainPartName) == "string" and bundle.mainPartName or ""
  if mainPartName == "" and type(vdata.mainPartName) == "string" then
    mainPartName = vdata.mainPartName
  end

  local chosen, chosenSource, configTable = {}, "none", nil
  for _, candidate in ipairs(configCandidates(bundle, vdata)) do
    local map, n = stringMap(candidate.parts)
    if n > 0 then
      chosen, chosenSource, configTable = map, candidate.name, candidate.config
      break
    end
    configTable = configTable or candidate.config
  end
  local fromConfig = countKeys(chosen)
  local fromRows = deriveFromRows(vdata.flexbodies, chosen) + deriveFromRows(vdata.props, chosen)
  local inferred = 0
  if type(vdata.activeParts) == "table" then
    local ok, count = pcall(inferIntermediate, vdata.activeParts, mainPartName, chosen)
    if ok then inferred = count end
  end

  local flexbodies = flexbodyRows(vdata.flexbodies)
  local props = propRows(vdata.props, vdata.nodes)

  local payload = {
    schema = "beamSkinStudio.vehicleParts",
    version = 1,
    angleUnit = "deg",
    model = model,
    mainPartName = mainPartName,
    mainPartPath = "/" .. (mainPartName ~= "" and mainPartName or model),
    configuration = configTable and type(configTable.Configuration) == "string" and configTable.Configuration or nil,
    vars = plainVars(configTable and configTable.vars),
    chosenParts = chosen,
    parts = parts,
    meshNames = meshNames,
    flexbodies = flexbodies,
    props = props,
    debug = {
      chosenSource = chosenSource,
      chosenFromConfig = fromConfig,
      chosenFromRows = fromRows,
      chosenInferred = inferred,
      chosenTotal = countKeys(chosen),
      activeParts = activeCount,
      flexbodyRows = #flexbodies,
      propRows = #props
    }
  }

  local ok, err = pcall(jsonWriteFile, exportPath, payload, true)
  if not ok then
    report(false, "Could not write " .. exportPath .. ": " .. tostring(err))
    return false
  end

  report(true, "Exported " .. #meshNames .. " meshes, " .. countKeys(chosen) .. " slot entries ("
    .. chosenSource .. ") to " .. exportPath)
  return true
end

return M
