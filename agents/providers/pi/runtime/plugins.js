import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {imageEngine} from './image-engine.js';

const imageBudgetKeys = new Set([
  'maxRequestBytes', 'maxImages', 'maxInlineImageBytes', 'maxImageDimension',
  'denseImageCount', 'denseImageDimension', 'protectRecent', 'compress',
  'compressMaxDimension', 'compressMaxBytes',
]);
const registry = {
  'image-budget': {
    entrypoint: fileURLToPath(new URL('../plugins/image-budget.ts', import.meta.url)),
    validateOptions(options) {
      for (const [key, value] of Object.entries(options)) {
        if (!imageBudgetKeys.has(key)) throw Error('unknown image-budget option: ' + key);
        if (key === 'compress' ? typeof value !== 'boolean' : !Number.isSafeInteger(value) || value < (key === 'protectRecent' ? 0 : 1)) {
          throw Error('invalid image-budget option: ' + key);
        }
      }
    },
    validateSelection(options) {
      for (const key of ['maxRequestBytes', 'maxImages']) {
        if (!Object.hasOwn(options, key)) throw Error('image-budget requires ' + key);
      }
      if (Object.hasOwn(options, 'denseImageCount') !== Object.hasOwn(options, 'denseImageDimension')) {
        throw Error('image-budget requires denseImageCount and denseImageDimension together');
      }
      if (options.denseImageDimension > (options.maxImageDimension ?? 2000)) {
        throw Error('denseImageDimension must not exceed maxImageDimension');
      }
      if (options.protectRecent > options.maxImages) throw Error('protectRecent must not exceed maxImages');
    },
    validateModel(model) {
      if (model.api !== 'openai-completions' || !model.input?.includes('image')) {
        throw Error('image-budget requires a supported OpenAI-compatible image model');
      }
    },
  },
};
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

export function pluginOptions(input = {}, definitions = registry) {
  if (!object(input)) throw Error('Pi plugins must be an object');
  return Object.fromEntries(Object.entries(input).map(([id, options]) => {
    if (!Object.hasOwn(definitions, id)) throw Error('unknown managed Pi plugin: ' + id);
    if (!object(options)) throw Error('Pi plugin options must be an object: ' + id);
    definitions[id].validateOptions(options);
    return [id, {...options}];
  }));
}

export function selectPlugins(global, profile, definitions = registry) {
  return Object.fromEntries(Object.keys(definitions)
    .filter(id => Object.hasOwn(global, id) || Object.hasOwn(profile, id))
    .map(id => {
      const options = {...global[id], ...profile[id]};
      definitions[id].validateSelection(options);
      return [id, options];
    }));
}

export function pluginLaunch(plugins, model, profile, definitions = registry, engineOwner) {
  if (!Object.keys(plugins).length) return {entries: [], options: ''};
  const entries = Object.keys(plugins).map(id => {
    const definition = definitions[id];
    definition.validateModel(model);
    if (!fs.statSync(definition.entrypoint).isFile()) throw Error('missing managed Pi plugin: ' + id);
    return definition.entrypoint;
  });
  const route = {provider: model.provider, id: model.id, api: model.api, baseUrl: normalizeEndpoint(model.baseUrl)};
  const engine = engineOwner && Object.hasOwn(plugins,'image-budget') ? imageEngine(engineOwner.base,engineOwner.root) : undefined;
  return {entries, options: JSON.stringify({route, plugins, profile, engine})};
}

export function normalizeEndpoint(value) {
  const url = new URL(value);
  if (url.username || url.password || url.search || url.hash ||
      !(url.protocol === 'https:' || (url.protocol === 'http:' && url.hostname === '127.0.0.1'))) {
    throw Error('managed Pi plugin requires a plain HTTPS or loopback HTTP endpoint');
  }
  return url.origin + url.pathname.replace(/\/+$/, '');
}

export async function checkNativeArgs(cli, args) {
  const packageDir = path.resolve(path.dirname(cli), '../..');
  const {parseArgs} = await import(pathToFileURL(path.join(packageDir, 'dist/cli/args.js')));
  const parsed = parseArgs(args);
  if (parsed.noExtensions) throw Error('managed Pi requires its permission extension; remove --no-extensions or -ne');
  for (const source of parsed.extensions ?? []) {
    if (source.startsWith('builtin:')) continue;
    if ((!path.isAbsolute(source) && !/^\.{1,2}[\\/]/.test(source)) ||
        /^(?:[\\/]{2})/.test(source) || !fs.existsSync(source)) {
      throw Error('managed Pi requires an existing explicit local extension path');
    }
  }
}
