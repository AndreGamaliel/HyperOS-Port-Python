# Port ROM Cache System

## Overview

The Port ROM Cache mechanism is a hierarchical caching system designed to speed up the ROM porting process across multiple devices. It allows the processing output of a given Port ROM (extracted partitions and modified APKs) to be reused across different target device porting tasks, significantly reducing redundant work.

## Features

- **Hierarchical Caching**: Supports partition-level caching (Level 1) and APK modification caching (Level 2).
- **File Locking**: Concurrency-safe, supporting multi-process concurrent access.
- **Version Control**: Automatic cache invalidation based on ROM hash and modifier versioning.
- **Integrity Verification**: Automatic verification of cache consistency with repair support.

## Usage

### Basic Usage

Caching is enabled by default:

```bash
python main.py --stock stock.zip --port port.zip
```

### CLI Arguments

| Argument | Description | Default |
|------|------|--------|
| `--cache-dir` | Path to cache directory | `.cache/portroms` |
| `--no-cache` | Disable cache, force full extraction and modification | - |
| `--clear-cache` | Clear all cache before starting | - |
| `--show-cache-stats` | Display cache statistics and exit | - |

### Inspect Cache Statistics

```bash
python main.py --show-cache-stats
```

Example Output:
```json
{
  "version": "1.0",
  "cache_root": ".cache/portroms",
  "total_size_bytes": 2147483648,
  "total_size_mb": 2048.0,
  "cached_roms": [
    {
      "hash": "a1b2c3d4...",
      "partitions": [
        {"name": "system", "size_mb": 1024.0},
        {"name": "product", "size_mb": 512.0}
      ],
      "total_size_bytes": 1610612736
    }
  ]
}
```

### Disable Caching

```bash
python main.py --stock stock.zip --port port.zip --no-cache
```

### Clear Cache

```bash
# Clear all cache
python main.py --stock stock.zip --port port.zip --clear-cache

# Or use the standalone cache manager tool
python tools/cache_manager.py clean --all
```

## Cache Manager Tool

### List Cached ROMs

```bash
python tools/cache_manager.py list
```

### View Detailed Statistics

```bash
python tools/cache_manager.py stats
```

### Verify Cache Integrity

```bash
# Verify only
python tools/cache_manager.py verify

# Verify and repair
python tools/cache_manager.py verify --fix
```

## Cache Structure

```
.cache/portroms/
├── metadata.json              # Global cache metadata
├── a1b2c3d4e5f6.../          # ROM hash directory (first 16 characters)
│   ├── partitions/           # Partition cache
│   │   ├── system/          # system partition
│   │   │   ├── app/
│   │   │   ├── framework/
│   │   │   └── cache_metadata.json
│   │   ├── product/         # product partition
│   │   └── ...
│   └── apks/                 # APK modification cache
│       └── MIUIPackageInstaller_<hash>_InstallerModifier_v1.0/
│           ├── modified.apk
│           └── metadata.json
└── ...
```

## How It Works

### Partition Cache Workflow

```
Extraction Phase:
  1. Check global cache for requested partition.
  2. If found, restore directly from cache into work directory.
  3. If missing, extract normally and save into cache.

Modification Phase:
  1. Execute modifications on the extracted partition.
  2. (Future) Cache fully modified partitions.
```

### APK Cache Workflow

```
APK Modification:
  1. Compute APK cache key (APK hash + modifier class name + version).
  2. Check cache for modified APK.
  3. If found, copy cached APK directly to destination.
  4. If missing, decompile, patch, and recompile.
  5. Save modified APK into cache.
```

## Performance Comparison

| Scenario | Without Cache | With Cache | Time Saved |
|------|--------|--------|---------|
| First port | 15 min | 15 min | 0% |
| Same Port ROM, different device | 15 min | 5-8 min | 50-70% |
| Config changes only (repack) | 15 min | 3-5 min | 70-80% |

## Invalidation Policies

Cache invalidates automatically under the following conditions:

1. **ROM File Changes**: File hash mismatch.
2. **Cache Version Upgrades**: Format version bump.
3. **APK Modifier Version Changes**: `cache_version` attribute bump.
4. **Integrity Failures**: Missing files or corrupted checksums.

## Important Notes

1. **Location**: Defaults to `.cache/portroms/` in the project root. Ensure sufficient disk space.
2. **Concurrency**: File locks protect against race conditions, but concurrent modifications of the same ROM may still conflict.
3. **Cleanup**: Manual cleanup for now; automated policies planned.
4. **Device-Specific Files**: Vendor/ODM partitions and firmware images are never cached as they are device-specific.

## Troubleshooting

### Cache Misses

If cache misses occur unexpectedly, check:
1. Ensure `--no-cache` was not accidentally passed.
2. Verify ROM file hash has not changed.
3. Verify cache directory write permissions.

### Repair Corrupted Cache

```bash
# Verify and auto-repair
python tools/cache_manager.py verify --fix

# Or clear all cache to start fresh
python tools/cache_manager.py clean --all
```

## Roadmap

- [ ] Automatic cache size limits and LRU eviction.
- [ ] Compressed caching to save disk storage.
- [ ] Distributed cache support across multiple worker machines.
- [ ] Background cache preloading and synchronization.
