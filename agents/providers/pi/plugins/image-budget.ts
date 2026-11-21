import {createHash} from 'node:crypto';
import {resizeImage} from '@earendil-works/pi-coding-agent';
import {normalizeEndpoint} from '../runtime/plugins.js';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

function imageUrl(part) {
  return part?.type === 'image_url' ? part.image_url?.url : undefined;
}

function inline(url,imageDimensions) {
  if (typeof url !== 'string') throw Error('image URL is missing');
  const match = /^data:(image\/(?:png|jpeg|webp|gif));base64,/.exec(url);
  if (!match) throw Error('unsupported inline image format');
  const data = url.slice(match[0].length);
  if (!data || data.length % 4 !== 0 || !/^[A-Za-z0-9+/]+={0,2}$/.test(data)) {
    throw Error('invalid inline image encoding');
  }
  const dimensions = imageDimensions(data, match[1]);
  if (!dimensions?.width || !dimensions.height) throw Error('unknown inline image dimensions');
  return {
    data, mime: match[1],
    bytes: data.length / 4 * 3 - (data.endsWith('==') ? 2 : data.endsWith('=') ? 1 : 0),
    dimension: Math.max(dimensions.width, dimensions.height),
  };
}

function imageParts(payload) {
  if (!Array.isArray(payload?.messages)) throw Error('unknown OpenAI request shape');
  return payload.messages.flatMap(message => Array.isArray(message.content)
    ? message.content.filter(part => part?.type === 'image_url') : []);
}

function routeMatches(model, route) {
  try {
    return model?.provider === route.provider && model.id === route.id && model.api === route.api &&
      normalizeEndpoint(model.baseUrl) === route.baseUrl;
  } catch {return false;}
}

function confirmedRejection(message,classifyError) {
  const text = message.errorMessage ?? '';
  if (/^(?:[^\n]+ API error \(413\):|413(?:\s|:|$))/i.test(text) &&
      !/context[_ ]length[_ ]exceeded|context window|(?:maximum|too many) (?:input )?tokens/i.test(text)) {
    return {kind:'request-bytes'};
  }
  if (!/^(?:[^\n]+ API error \(400\):|400(?:\s|:|$))/i.test(text)) return undefined;
  const rejection = classifyError(text);
  return rejection?.kind === 'image-count' && rejection.quotedLimit ? rejection : undefined;
}

function sameFailure(entry, message) {
  return entry?.type === 'message' && entry.message?.role === 'assistant' &&
    entry.message.stopReason === 'error' && entry.message.timestamp === message.timestamp &&
    entry.message.provider === message.provider && entry.message.model === message.model &&
    entry.message.errorMessage === message.errorMessage;
}

function failedEntry(branch, failure) {
  const last = branch.findLast(entry => entry.type === 'message' && entry.message?.role === 'assistant');
  if (!sameFailure(last, failure)) return undefined;
  return last;
}

export default async function imageBudget(pi) {
  const launch = JSON.parse(process.env.PI_SOT_PLUGINS ?? 'null');
  const options = launch?.plugins?.['image-budget'];
  if (!options) return;

  const load = name => import(pathToFileURL(path.join(launch.engine,'src',name+'.ts')).href);
  const [{planImageBudget},{DEFAULT_CONFIG},{classifyError},{imageDimensions},{jsonSize},{scrubPayload},{ImageProcessor}]
    = await Promise.all(['budget','config','errors','image','json-size','payload','resize'].map(load));
  const measured = payload => ({payload, bytes:jsonSize(payload), count:imageParts(payload).length});

  const limits = {
    ...DEFAULT_CONFIG, ...options, dedupe:false,
    maxImageBytes:Infinity, maxBytesPerImage:4 * Math.ceil((options.maxInlineImageBytes ?? 32 * 1024 ** 2) / 3),
    protectRecent:options.protectRecent ?? Math.min(2,options.maxImages),
  };
  const historyType = 'genosai-image-budget';
  const routeKey = createHash('sha256').update(JSON.stringify(launch)).digest('hex');
  const learned = ctx => {
    const entry = ctx.sessionManager.getBranch().findLast(
      item=>item.type==='custom' && item.customType===historyType && item.data?.key===routeKey);
    const valid = (value,fallback) => Number.isSafeInteger(value) && value>0 ? Math.min(value,fallback) : fallback;
    return {bytes:valid(entry?.data?.bytes,limits.maxRequestBytes),count:valid(entry?.data?.count,limits.maxImages)};
  };
  const processor = new ImageProcessor({resize:resizeImage});
  const transform = (data, mime, maxDimension, maxBytes) =>
    processor.process(processor.hashOf('',data),data,mime,{maxDimension,maxBytes});
  const matches = ctx => routeMatches(ctx.model,launch.route);
  const report = (ctx, message, level='error') => {
    if (ctx.hasUI) ctx.ui.notify('image-budget: '+message,level);
    else console.error('image-budget: '+message);
  };
  const refuse = (ctx, reason) => {
    report(ctx, 'request refused: '+reason);
    ctx.abort();
  };
  const protectIds = new Set();
  const knownUrls = new Set();
  let contextKnown = false;
  let last, pending, retryLimit;
  let recovered = false;
  const clear = () => {last = pending = retryLimit = undefined; protectIds.clear(); knownUrls.clear(); contextKnown = false;};
  const reset = () => {clear(); recovered = false;};
  for (const event of ['session_start','session_tree','input','model_select','agent_settled']) {
    pi.on(event, reset);
  }

  async function finalize(payload, maxBytes, maxImages, protect) {
    const candidate = structuredClone(payload);
    const fixed = imageParts(candidate).filter(protect);
    // Keep protected images in the measured body while excluding them from the removal pass.
    for (const part of fixed) part.type = 'protected';
    const target = scrubPayload(candidate,jsonSize(candidate),maxBytes,0,{maxImages:Math.max(0,maxImages-fixed.length)});
    for (const part of fixed) part.type = 'image_url';
    const parts = imageParts(target.payload);
    const maxDimension = parts.length >= (options.denseImageCount ?? Infinity)
      ? options.denseImageDimension : limits.maxImageDimension;
    for (const part of parts) {
      const img = inline(imageUrl(part),imageDimensions);
      if (img.bytes > (options.maxInlineImageBytes ?? 32 * 1024 ** 2) || img.dimension > maxDimension) {
        const reduced = await transform(img.data,img.mime,maxDimension,
          Math.min(limits.maxBytesPerImage,limits.compressMaxBytes));
        if (!reduced) throw Error('an image could not be resized within the route limits');
        part.image_url = {...part.image_url,url:'data:'+reduced.mimeType+';base64,'+reduced.data};
        const checked = inline(imageUrl(part),imageDimensions);
        if (checked.bytes > (options.maxInlineImageBytes ?? 32 * 1024 ** 2) || checked.dimension > maxDimension) {
          throw Error('resized image still exceeds the route limits');
        }
      }
    }
    const result = measured(candidate);
    if (result.bytes > maxBytes || result.count > maxImages) {
      throw Error(`${result.bytes} bytes, ${result.count} images exceed the configured request limits`);
    }
    return {...result, omitted:target.removed};
  }

  pi.on('context', async ({messages},ctx) => {
    protectIds.clear();
    knownUrls.clear();
    contextKnown = false;
    if (!matches(ctx)) return;
    // Only a completed answer closes the image protection boundary.
    const lastAnswer = messages.findLastIndex(m=>m.role==='assistant' && m.stopReason==='stop');
    const images = messages.flatMap((message,index) => Array.isArray(message.content)
      ? message.content.filter(part => part.type==='image').map(part=>({index,data:part.data})) : []);
    const recent = new Set((limits.protectRecent ? images.slice(-limits.protectRecent) : []).map(image=>image.data));
    const active = retryLimit ?? learned(ctx);
    try {
      const fixed = new Map();
      const planning = messages.map((message,index) => {
        if (!Array.isArray(message.content)) return message;
        const content = message.content.map(part => {
          if (part.type!=='image' || (index<=lastAnswer && !recent.has(part.data))) return part;
          const protectedImage={...part,type:'fixed'};
          fixed.set(protectedImage,part);
          return protectedImage;
        });
        return {...message,content};
      });
      const plan = await planImageBudget({
        messages:planning,
        limits:{...limits,maxRequestBytes:active.bytes,maxImages:Math.max(0,active.count-fixed.size),protectRecent:0},
        sticky:new Map(),overheadBytes:0,
        transform:(ref,spec)=>transform(ref.block.data,ref.mimeType,spec.maxDimension,spec.maxBytes),
      });
      const output = plan.messages.map(message => Array.isArray(message.content)
        ? {...message,content:message.content.map(part=>fixed.get(part)??part)} : message);
      const outgoing = output.flatMap((message,index) => Array.isArray(message.content)
        ? message.content.filter(part=>part.type==='image')
          .map(part=>({index,url:'data:'+part.mimeType+';base64,'+part.data}))
        : []);
      const keepStart = outgoing.length-limits.protectRecent;
      for (const [position,{index,url}] of outgoing.entries()) {
        knownUrls.add(url);
        if (index>lastAnswer || position>=keepStart) protectIds.add(url);
      }
      contextKnown = true;
      if (plan.stats.omittedImages || plan.stats.resizedImages) {
        report(ctx,`${outgoing.length} images kept, ${plan.stats.omittedImages} omitted, ${plan.stats.resizedImages} resized`,'warning');
      }
      return plan.changed ? {messages:output} : undefined;
    } catch {
      // A caught context hook error must still prevent dispatch.
      contextKnown = false;
    }
  });

  pi.on('before_provider_request', async ({payload},ctx) => {
    last = pending = undefined;
    if (!matches(ctx)) return;
    if (!contextKnown) return refuse(ctx,'image protection could not be established');
    const active = retryLimit ?? learned(ctx);
    try {
      const protectedUrls = new Set(protectIds);
      const known = new Set(knownUrls);
      const protect = part => protectedUrls.has(imageUrl(part)) || !known.has(imageUrl(part));
      const result = await finalize(payload,active.bytes,active.count,protect);
      if (retryLimit && (retryLimit.kind==='request-bytes' ? result.bytes>=retryLimit.previous : result.count>=retryLimit.previous)) {
        return refuse(ctx,'recovery did not reduce the rejected request metric');
      }
      last = {...result,protect};
      if (result.omitted) report(ctx,`${result.omitted} older images omitted from ${result.bytes} byte request`,'warning');
      return result.payload;
    } catch (error) {
      refuse(ctx,error.message);
    }
  });

  pi.on('message_end',async ({message},ctx) => {
    if (message.role!=='assistant') return;
    pending = undefined;
    if (!matches(ctx) || recovered || !last?.count || message.stopReason!=='error' ||
        message.provider!==launch.route.provider || message.model!==launch.route.id) return;
    const rejection = confirmedRejection(message,classifyError);
    if (!rejection) return;
    const active = learned(ctx);
    const bytes = rejection.kind==='request-bytes' ? Math.min(active.bytes,Math.floor(last.bytes*0.9)) : active.bytes;
    const count = rejection.kind==='image-count' ? Math.min(active.count,rejection.quotedLimit) : active.count;
    try {
      const reduced = await finalize(last.payload,bytes,count,last.protect);
      const previous = rejection.kind==='request-bytes' ? last.bytes : last.count;
      const next = rejection.kind==='request-bytes' ? reduced.bytes : reduced.count;
      if (next<previous) pending = {message,bytes,count,previous,kind:rejection.kind};
    } catch {
      // There is no proven smaller candidate. Pi retains control of overflow recovery.
    }
  });

  pi.on('session_before_compact',(event,ctx) => {
    if (pending && matches(ctx) && event.reason==='overflow' && event.willRetry &&
        failedEntry(event.branchEntries,pending.message)) return {cancel:true};
  });

  pi.on('session_compact',clear);
  pi.on('agent_before_settle',(event,ctx) => {
    if (!matches(ctx)) return;
    if (recovered) {
      if (event.outcome==='completed' && retryLimit && last) {
        const {bytes,count} = retryLimit;
        return {entries:[...event.entries,{type:'custom',customType:historyType,data:{key:routeKey,bytes,count}}]};
      }
      return;
    }
    if (!pending) return;
    const entry = failedEntry(ctx.sessionManager.getBranch(),pending.message);
    if (!entry) return;
    const visible = event.context.contextEntries.find(item=>item.sourceEntry.id===entry.id)?.messages ?? [];
    if (!visible.length && !event.context.canContinue) return;
    if (visible.some(message=>Array.isArray(message.content) && message.content.some(part=>part.type==='toolCall'))) return;
    recovered = true;
    retryLimit = pending;
    pending = undefined;
    report(ctx,'retrying once with a smaller request','warning');
    return {continue:true,...(visible.length ? {entries:[...event.entries,{type:'context_edit',targetId:entry.id,replacement:null}]} : {})};
  });
}
