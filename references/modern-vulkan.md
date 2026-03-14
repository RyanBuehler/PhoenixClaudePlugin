# Modern Vulkan Quick Reference (1.2–1.4)

Practical reference for modern Vulkan features in a game engine context.

## Dynamic Rendering (Vulkan 1.3)

Eliminates `VkRenderPass` and `VkFramebuffer` objects for simpler rendering setup.

### Before (Legacy)

```cpp
// Create VkRenderPass with subpass descriptions
// Create VkFramebuffer for each swapchain image
// vkCmdBeginRenderPass(cmd, &beginInfo, VK_SUBPASS_CONTENTS_INLINE);
// ... draw ...
// vkCmdEndRenderPass(cmd);
```

### After (Dynamic Rendering)

```cpp
VkRenderingAttachmentInfo colorAttachment{};
colorAttachment.sType = VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO;
colorAttachment.imageView = swapchainImageView;
colorAttachment.imageLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
colorAttachment.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
colorAttachment.clearValue.color = {{0.0f, 0.0f, 0.0f, 1.0f}};

VkRenderingInfo renderInfo{};
renderInfo.sType = VK_STRUCTURE_TYPE_RENDERING_INFO;
renderInfo.renderArea = {{0, 0}, extent};
renderInfo.layerCount = 1;
renderInfo.colorAttachmentCount = 1;
renderInfo.pColorAttachments = &colorAttachment;
renderInfo.pDepthAttachment = &depthAttachment;

vkCmdBeginRendering(cmd, &renderInfo);
// ... draw ...
vkCmdEndRendering(cmd);
```

**Benefits:** No upfront render pass/framebuffer creation, flexible attachment configuration per draw.

**Pipeline creation:** Set `VkPipelineRenderingCreateInfo` in `pNext` instead of `renderPass`.

## Synchronization2 (Vulkan 1.3)

Cleaner barrier API with expanded stage/access flags.

### Before (Legacy Barriers)

```cpp
VkImageMemoryBarrier barrier{};
barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
barrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
barrier.oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
// ...
vkCmdPipelineBarrier(cmd,
    VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
    VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
    0, 0, nullptr, 0, nullptr, 1, &barrier);
```

### After (Synchronization2)

```cpp
VkImageMemoryBarrier2 barrier{};
barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2;
barrier.srcStageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT;
barrier.srcAccessMask = VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT;
barrier.dstStageMask = VK_PIPELINE_STAGE_2_FRAGMENT_SHADER_BIT;
barrier.dstAccessMask = VK_ACCESS_2_SHADER_SAMPLED_READ_BIT;
barrier.oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
barrier.image = image;
barrier.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};

VkDependencyInfo depInfo{};
depInfo.sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO;
depInfo.imageMemoryBarrierCount = 1;
depInfo.pImageMemoryBarriers = &barrier;

vkCmdPipelineBarrier2(cmd, &depInfo);
```

**Key changes:**
- Stages and access masks are per-barrier (not per-call)
- 64-bit flags with more precise stages (`COPY`, `RESOLVE`, `BLIT`, `CLEAR`)
- `VK_ACCESS_2_SHADER_SAMPLED_READ_BIT` replaces generic `VK_ACCESS_SHADER_READ_BIT`

### New Stage/Access Flags

| Sync2 Stage | Replaces |
|-------------|----------|
| `COPY_BIT` | `TRANSFER_BIT` (for copies) |
| `RESOLVE_BIT` | `TRANSFER_BIT` (for resolves) |
| `BLIT_BIT` | `TRANSFER_BIT` (for blits) |
| `CLEAR_BIT` | `TRANSFER_BIT` (for clears) |
| `ALL_COMMANDS_BIT` | `ALL_COMMANDS_BIT` (same, but 64-bit) |

## Timeline Semaphores (Vulkan 1.2)

Counter-based semaphores for flexible GPU-GPU and CPU-GPU synchronization.

```cpp
// Create timeline semaphore
VkSemaphoreTypeCreateInfo timelineInfo{};
timelineInfo.sType = VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO;
timelineInfo.semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE;
timelineInfo.initialValue = 0;

VkSemaphoreCreateInfo semInfo{};
semInfo.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;
semInfo.pNext = &timelineInfo;

VkSemaphore timeline;
vkCreateSemaphore(device, &semInfo, nullptr, &timeline);
```

### GPU Signal/Wait

```cpp
// Submit with timeline wait/signal
VkTimelineSemaphoreSubmitInfo timelineSubmit{};
timelineSubmit.sType = VK_STRUCTURE_TYPE_TIMELINE_SEMAPHORE_SUBMIT_INFO;
timelineSubmit.waitSemaphoreValueCount = 1;
uint64_t waitValue = 5;
timelineSubmit.pWaitSemaphoreValues = &waitValue;
timelineSubmit.signalSemaphoreValueCount = 1;
uint64_t signalValue = 6;
timelineSubmit.pSignalSemaphoreValues = &signalValue;

VkSubmitInfo submit{};
submit.pNext = &timelineSubmit;
// ... rest of submit info
```

### CPU Wait/Signal

```cpp
// CPU waits for GPU to reach value
VkSemaphoreWaitInfo waitInfo{};
waitInfo.sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO;
waitInfo.semaphoreCount = 1;
waitInfo.pSemaphores = &timeline;
uint64_t waitVal = 10;
waitInfo.pValues = &waitVal;
vkWaitSemaphores(device, &waitInfo, UINT64_MAX);

// CPU signals (advance counter)
VkSemaphoreSignalInfo signalInfo{};
signalInfo.sType = VK_STRUCTURE_TYPE_SEMAPHORE_SIGNAL_INFO;
signalInfo.semaphore = timeline;
signalInfo.value = 11;
vkSignalSemaphore(device, &signalInfo);
```

**Replaces:** Multiple binary semaphores and fences with a single timeline semaphore.

## Buffer Device Address (Vulkan 1.2)

Access buffers via GPU pointers instead of descriptor bindings.

```cpp
// Enable at device creation
VkPhysicalDeviceBufferDeviceAddressFeatures bdaFeatures{};
bdaFeatures.bufferDeviceAddress = VK_TRUE;

// Create buffer with device address flag
VkBufferCreateInfo bufInfo{};
bufInfo.usage |= VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT;

// Get the address
VkBufferDeviceAddressInfo addrInfo{};
addrInfo.sType = VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO;
addrInfo.buffer = buffer;
VkDeviceAddress addr = vkGetBufferDeviceAddress(device, &addrInfo);

// Pass to shader via push constants or another buffer
```

**In shaders:**
```glsl
#extension GL_EXT_buffer_reference : require

layout(buffer_reference, std430) readonly buffer VertexBuffer
{
    vec4 positions[];
};

layout(push_constant) uniform PushConstants
{
    VertexBuffer vertexData;  // 64-bit GPU pointer
} pc;

void main()
{
    vec4 pos = pc.vertexData.positions[gl_VertexIndex];
}
```

## Descriptor Indexing (Vulkan 1.2)

Bindless resources — index into arrays of descriptors from shaders.

### Setup

```cpp
// Enable features
VkPhysicalDeviceDescriptorIndexingFeatures indexingFeatures{};
indexingFeatures.shaderSampledImageArrayNonUniformIndexing = VK_TRUE;
indexingFeatures.descriptorBindingSampledImageUpdateAfterBind = VK_TRUE;
indexingFeatures.descriptorBindingPartiallyBound = VK_TRUE;
indexingFeatures.runtimeDescriptorArray = VK_TRUE;

// Create binding with variable count and update-after-bind
VkDescriptorSetLayoutBinding binding{};
binding.binding = 0;
binding.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
binding.descriptorCount = MAX_TEXTURES;  // e.g., 16384
binding.stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

VkDescriptorBindingFlags flags =
    VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT |
    VK_DESCRIPTOR_BINDING_UPDATE_AFTER_BIND_BIT |
    VK_DESCRIPTOR_BINDING_VARIABLE_DESCRIPTOR_COUNT_BIT;
```

### In Shaders

```glsl
#extension GL_EXT_nonuniform_qualifier : require

layout(set = 0, binding = 0) uniform sampler2D textures[];

void main()
{
    uint texIndex = materialData.albedoIndex;
    vec4 color = texture(textures[nonuniformEXT(texIndex)], uv);
}
```

**Replaces:** Fixed descriptor sets per material with one global texture array.

## Descriptor Buffers (VK_EXT_descriptor_buffer)

Replace descriptor pools and sets with raw buffer memory containing descriptors.

```cpp
// Get descriptor size
VkDeviceSize descriptorSize;
vkGetDescriptorSetLayoutSizeEXT(device, layout, &descriptorSize);

// Allocate buffer for descriptors
VkBufferCreateInfo bufInfo{};
bufInfo.usage = VK_BUFFER_USAGE_RESOURCE_DESCRIPTOR_BUFFER_BIT_EXT;
bufInfo.size = descriptorSize * maxSets;

// Write descriptors directly to buffer memory
VkDescriptorGetInfoEXT getInfo{};
getInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_GET_INFO_EXT;
getInfo.type = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
getInfo.data.pUniformBuffer = &bufferInfo;
vkGetDescriptorEXT(device, &getInfo, descriptorSize, mappedPtr);

// Bind descriptor buffer (not descriptor set)
vkCmdBindDescriptorBuffersEXT(cmd, 1, &bindingInfo);
vkCmdSetDescriptorBufferOffsetsEXT(cmd, bindPoint, layout, 0, 1, &index, &offset);
```

**Benefits:** Direct memory control, better CPU cache behavior, eliminates descriptor pool fragmentation.

## Mesh Shaders (VK_EXT_mesh_shader)

Replace vertex + geometry stages with a compute-like mesh pipeline.

```
Traditional:  Input Assembly → Vertex Shader → [Geometry Shader] → Rasterizer
Mesh:         Task Shader (optional) → Mesh Shader → Rasterizer
```

### Mesh Shader (GLSL)

```glsl
#extension GL_EXT_mesh_shader : require

layout(local_size_x = 32) in;
layout(triangles, max_vertices = 64, max_primitives = 126) out;

layout(location = 0) out vec3 outColor[];

void main()
{
    uint meshletIndex = gl_WorkGroupID.x;
    // Load meshlet data, emit vertices and primitives
    SetMeshOutputsEXT(vertexCount, primitiveCount);

    gl_MeshVerticesEXT[threadIndex].gl_Position = mvp * pos;
    outColor[threadIndex] = color;
    gl_PrimitiveTriangleIndicesEXT[threadIndex] = uvec3(i0, i1, i2);
}
```

**Benefits:** GPU-driven geometry processing, natural LOD and culling, eliminates vertex/index buffer bottlenecks.

## Maintenance Extensions

### VK_KHR_maintenance4 (Vulkan 1.3)

- Query image memory requirements without creating the image
- `VK_IMAGE_ASPECT_NONE` for clearing
- `maxBufferSize` device limit

### VK_KHR_maintenance5

- `vkCmdBindIndexBuffer2KHR` — bind index buffer with explicit size
- `VK_FORMAT_A1B5G5R5_UNORM_PACK16` format
- Pipeline creation feedback flags
- `vkGetRenderingAreaGranularity` for dynamic rendering

### VK_KHR_maintenance6

- Binding descriptor sets with push descriptors improvements
- `VkBindMemoryStatus` for error reporting on memory bind

## VMA (Vulkan Memory Allocator)

The recommended way to manage Vulkan memory.

### Basic Usage

```cpp
#include "vk_mem_alloc.h"

// Create allocator
VmaAllocatorCreateInfo allocatorInfo{};
allocatorInfo.vulkanApiVersion = VK_API_VERSION_1_3;
allocatorInfo.physicalDevice = physicalDevice;
allocatorInfo.device = device;
allocatorInfo.instance = instance;
allocatorInfo.flags = VMA_ALLOCATOR_CREATE_BUFFER_DEVICE_ADDRESS_BIT;

VmaAllocator allocator;
vmaCreateAllocator(&allocatorInfo, &allocator);
```

### Creating Buffers

```cpp
// GPU-only buffer (vertex, index, uniform)
VkBufferCreateInfo bufInfo{};
bufInfo.size = dataSize;
bufInfo.usage = VK_BUFFER_USAGE_VERTEX_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;

VmaAllocationCreateInfo allocInfo{};
allocInfo.usage = VMA_MEMORY_USAGE_AUTO;
allocInfo.flags = VMA_ALLOCATION_CREATE_DEDICATED_MEMORY_BIT;  // For large buffers

VkBuffer buffer;
VmaAllocation allocation;
vmaCreateBuffer(allocator, &bufInfo, &allocInfo, &buffer, &allocation, nullptr);
```

### Staging Buffer (CPU → GPU Transfer)

```cpp
VmaAllocationCreateInfo stagingAllocInfo{};
stagingAllocInfo.usage = VMA_MEMORY_USAGE_AUTO;
stagingAllocInfo.flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT |
                         VMA_ALLOCATION_CREATE_MAPPED_BIT;

VkBuffer stagingBuffer;
VmaAllocation stagingAlloc;
VmaAllocationInfo stagingInfo;
vmaCreateBuffer(allocator, &bufInfo, &stagingAllocInfo,
    &stagingBuffer, &stagingAlloc, &stagingInfo);

// Write directly to mapped memory
memcpy(stagingInfo.pMappedData, sourceData, dataSize);
```

### Memory Types

| VMA Usage | Meaning | Use Case |
|-----------|---------|----------|
| `AUTO` | Let VMA decide | Default for most allocations |
| `AUTO_PREFER_DEVICE` | Prefer GPU memory | Textures, vertex buffers |
| `AUTO_PREFER_HOST` | Prefer CPU-visible | Staging, readback |

## Vulkan 1.4 Highlights

Vulkan 1.4 (ratified 2025) promotes several extensions to core:

- **Dynamic rendering** — core (no extension needed)
- **Push descriptors** — `VK_KHR_push_descriptor` promoted
- **Maintenance5/6** — core
- **Extended dynamic state** — more pipeline state set dynamically
- **Shader object** — `VK_EXT_shader_object` (simplified pipeline management)

### Extended Dynamic State

Reduce pipeline object explosion by setting more state dynamically:

```cpp
// Set at draw time instead of pipeline creation
vkCmdSetCullMode(cmd, VK_CULL_MODE_BACK_BIT);
vkCmdSetFrontFace(cmd, VK_FRONT_FACE_COUNTER_CLOCKWISE);
vkCmdSetPrimitiveTopology(cmd, VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST);
vkCmdSetDepthTestEnable(cmd, VK_TRUE);
vkCmdSetDepthWriteEnable(cmd, VK_TRUE);
vkCmdSetDepthCompareOp(cmd, VK_COMPARE_OP_LESS);
vkCmdSetStencilTestEnable(cmd, VK_FALSE);
```
