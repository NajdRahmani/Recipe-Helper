/* Savour recipe UI — plain JavaScript, no build tooling or external packages.
 * The backend contract is POST { query, image_b64?, filters } -> recipe JSON.
 * Everything returned by AI or Qdrant is rendered as TEXT, not unsanitized HTML.
 */
'use strict';
const $ = id => document.getElementById(id);
const STORE = 'savour.v1.';
const DEFAULT_ENDPOINT = 'http://localhost:5678/webhook/recipe-helper';
const demoRecipe = {
  name: 'shakshuka', minutes: 30, kcal: null, protein_g: null, carbs_g: null, fat_g: null,
  cuisine_type: 'North African', vegetarian: true,
  ingredients: ['3 eggs', '4 tomatoes', '1 bell pepper', '1 onion', '2 garlic cloves', '2 tbsp olive oil', '1 tsp paprika', 'salt and pepper'],
  steps: ['Dice the onion, pepper and tomatoes; mince the garlic.', 'Warm the oil in a skillet and soften the onion and pepper.', 'Stir in garlic, paprika and tomatoes; simmer until the sauce thickens.', 'Make three wells, crack in the eggs and cover until the whites are set.', 'Serve warm with bread if desired.'],
  chef_note: 'A North African skillet dish with eggs cooked in a tomato and pepper sauce. Keep the heat gentle while the eggs set.',
  substitutions: [], have: [], missing: [], image_url: null,
  agentic_review: { status: 'preview' }, isDemo: true,
};
let recipe = null, photoFile = null, photoPreviewUrl = '', activeController = null, toastTimer = null, cookingStep = 0, lastFocus = null;
const safeStorage = {
  get(key, fallback) { try { const v = localStorage.getItem(STORE + key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(STORE + key, JSON.stringify(value)); } catch { toast('Could not save locally in this browser.', true); } }
};
let savedRecipes = safeStorage.get('saved', []);
let pantry = safeStorage.get('pantry', []);
if (!Array.isArray(savedRecipes)) savedRecipes = [];
if (!Array.isArray(pantry)) pantry = [];
const text = v => v == null ? '' : String(v);
const number = value => value == null || value === '' ? null : (Number.isFinite(Number(value)) ? Number(value) : null);
const trim = (v, max = 5000) => text(v).trim().slice(0, max);
const sentenceCase = s => trim(s).replace(/^\p{L}/u, c => c.toUpperCase());
const norm = s => trim(s).toLowerCase().replace(/\s+/g, ' ');
const recipeKey = r => `${norm(r.name)}|${r.minutes ?? ''}|${(r.ingredients || []).slice(0, 4).map(norm).join(',')}`;
const make = (tag, className, value) => { const el = document.createElement(tag); if (className) el.className = className; if (value != null) el.textContent = text(value); return el; };
function toast(message, error = false) {
  const node = $('toast'); node.textContent = message; node.classList.toggle('error', !!error); node.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { node.hidden = true; }, 3600);
}
function showMessage(message, info = false) { const node = $('message'); node.textContent = message; node.classList.toggle('info', info); node.hidden = !message; }
function updateSavedCount() { $('savedCount').textContent = savedRecipes.length; }
function setLoading(active) {
  $('loadingSection').hidden = !active; $('searchSubmit').disabled = active;
  $('searchSubmit').innerHTML = active ? 'Finding your recipe… <span>✳</span>' : 'Find my recipe <span>↗</span>';
}
function base64NoPrefix(dataUrl) { return dataUrl.split(',', 2)[1] || ''; }
function fileToDataUrl(blob) { return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error('Could not read the photo')); reader.onload = () => resolve(reader.result); reader.readAsDataURL(blob); }); }
async function optimizedImage(file) {
  const dataUrl = await fileToDataUrl(file);
  if (file.size < 850_000) return base64NoPrefix(dataUrl);
  // Downsize large photos for quicker local Ollama runs. Fine print remains more readable at 1500px.
  try {
    const image = new Image();
    await new Promise((resolve, reject) => { image.onload = resolve; image.onerror = reject; image.src = dataUrl; });
    const scale = Math.min(1, 1500 / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const ctx = canvas.getContext('2d'); if (!ctx) return base64NoPrefix(dataUrl);
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    return base64NoPrefix(canvas.toDataURL('image/jpeg', 0.88));
  } catch { return base64NoPrefix(dataUrl); }
}
function peelJSON(raw) {
  if (typeof raw !== 'string') return raw;
  let str = raw.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  try { return JSON.parse(str); } catch { return raw; }
}
function unwrapRecipe(raw) {
  let value = peelJSON(raw);
  for (let i = 0; i < 6; i++) {
    if (Array.isArray(value)) { value = value[0]; continue; }
    if (!value || typeof value !== 'object') break;
    if (value.error) throw new Error(text(value.error));
    if (Array.isArray(value.ingredients) && Array.isArray(value.steps)) return value;
    const next = value.final_json ?? value.json ?? value.response ?? value.data ?? value.result ?? value.output;
    if (next == null) break;
    value = peelJSON(next);
  }
  throw new Error('The server did not return a recipe JSON with ingredients and steps. Check the n8n response node.');
}
function normalizeRecipe(raw) {
  const r = unwrapRecipe(raw);
  const asStrings = v => (Array.isArray(v) ? v : typeof v === 'string' ? v.split('\n') : []).map(x => typeof x === 'object' && x !== null ? x.name ?? x.text ?? '' : x).map(v => trim(v, 600)).filter(Boolean);
  return {
    name: trim(r.name || r.title || 'Your recipe', 160), minutes: number(r.minutes), kcal: number(r.kcal ?? r.calories_per_serving),
    protein_g: number(r.protein_g), carbs_g: number(r.carbs_g), fat_g: number(r.fat_g),
    cuisine_type: trim(r.cuisine_type, 40), vegetarian: r.vegetarian === true,
    ingredients: asStrings(r.ingredients).slice(0, 45), steps: asStrings(r.steps).slice(0, 35),
    chef_note: trim(r.chef_note, 1200), substitutions: Array.isArray(r.substitutions) ? r.substitutions.slice(0, 5).map(s => ({missing: trim(s?.missing, 160), replace_with: trim(s?.replace_with, 200)})).filter(s => s.missing && s.replace_with) : [],
    have: asStrings(r.have), missing: asStrings(r.missing), pantry: asStrings(r.pantry),
    servings: trim(r.servings, 40), recipe_time: trim(r.recipe_time, 50), document_complete: r.document_complete,
    image_url: /^https?:\/\//i.test(trim(r.image_url)) ? trim(r.image_url, 1600) : null,
    agentic_review: r.agentic_review || {}, isDemo: !!r.isDemo,
  };
}
async function submitRequest() {
  if (activeController) return;
  const query = trim($('recipeQuery').value, 700);
  if (!query && !photoFile) return showMessage('Type a dish, list a few ingredients, or attach a photo to begin.');
  const endpoint = trim(safeStorage.get('endpoint', DEFAULT_ENDPOINT));
  if (!/^https?:\/\//i.test(endpoint) && !endpoint.startsWith('/')) return showMessage('Open Connection settings and enter a valid webhook URL.');
  showMessage('');
  const filters = {};
  if ($('maxMinutes').value) filters.max_minutes = Number($('maxMinutes').value);
  if ($('maxKcal').value && Number($('maxKcal').value) > 0) filters.max_kcal = Number($('maxKcal').value);
  if ($('minProtein').value && Number($('minProtein').value) > 0) filters.min_protein_g = Number($('minProtein').value);
  if ($('vegetarian').checked) filters.vegetarian = true;
  if ($('cuisine').value) filters.cuisine = $('cuisine').value;
  activeController = new AbortController();
  const ctrl = activeController;
  setLoading(true);
  $('loadingSection').scrollIntoView({behavior:'smooth',block:'center'});
  try {
    const body = { query, filters };
    if (photoFile) body.image_b64 = await optimizedImage(photoFile);
    const timeout = setTimeout(() => ctrl.abort('timeout'), 180000);
    let response;
    try {
      response = await fetch(endpoint, {method: 'POST', headers: {'Content-Type':'application/json'}, body:JSON.stringify(body), signal:ctrl.signal});
    } finally { clearTimeout(timeout); }
    const responseText = await response.text();
    if (!response.ok) throw new Error(`Webhook returned HTTP ${response.status}: ${responseText.slice(0, 240)}`);
    const parsed = peelJSON(responseText);
    const result = normalizeRecipe(parsed);
    recipe = result; renderRecipe(result);
    $('recipeResult').hidden = false;
    requestAnimationFrame(() => $('recipeResult').scrollIntoView({behavior:'smooth',block:'start'}));
  } catch (err) {
    if (ctrl.signal.aborted && ctrl.signal.reason !== 'timeout') { showMessage('Search cancelled.', true); }
    else if (ctrl.signal.aborted) showMessage('Your backend did not respond within 3 minutes. Check the n8n execution; your local models may still be running.');
    else if (err instanceof TypeError || /failed to fetch/i.test(err.message)) showMessage('Could not reach the webhook. Check the URL in Settings, that n8n is running, and your browser’s CORS/network settings.');
    else showMessage(err.message || 'Something went wrong. Please try again.');
  } finally { if (activeController === ctrl) activeController = null; setLoading(false); }
}
function tag(value) { const span = make('span', 'recipe-tag', value); $('recipeTags').append(span); }
function renderRecipe(r) {
  $('recipeTitle').textContent = sentenceCase(r.name);
  $('recipeSubheading').textContent = r.isDemo ? 'A taste of what your assistant can find.' : 'Picked for your kitchen, with a little help from AI.';
  const checked = r.agentic_review?.status === 'approved';
  const status = $('resultStatus'); status.classList.toggle('preview', !checked);
  status.replaceChildren(make('span', 'status-dot'), document.createTextNode(checked ? 'AI reviewed recipe' : r.isDemo ? 'Example recipe · preview' : 'Recipe result'));
  $('recipeTags').replaceChildren();
  if (r.minutes != null) tag(`◷  ${r.minutes} min`);
  else if (r.recipe_time) tag(`◷  ${r.recipe_time}`);
  if (r.servings) tag(`♧  Serves ${r.servings}`);
  if (r.cuisine_type) tag(`✳  ${sentenceCase(r.cuisine_type)}`);
  if (r.vegetarian) tag('❀  Vegetarian');
  if (!r.minutes && !r.cuisine_type && !r.vegetarian) tag('✳  Ready to make');
  $('recipeImage').replaceChildren();
  if (r.image_url) {
    const img = make('img'); img.alt = `Recipe image for ${r.name}`; img.loading='lazy'; img.src = r.image_url;
    img.onerror = () => { $('recipeImage').replaceChildren(fallbackArt(r)); };
    $('recipeImage').append(img);
  } else $('recipeImage').append(fallbackArt(r));
  renderIngredients(r); renderSteps(r); renderNutrition(r);
  $('chefNote').textContent = r.chef_note || 'The most important ingredient is a little curiosity. Follow the steps above and enjoy the process.';
  $('subsArea').replaceChildren();
  if (r.substitutions.length) {
    const sub = make('p','subs-list', 'Smart swaps: ' + r.substitutions.map(s => `${s.missing} → ${s.replace_with}`).join(' • '));
    $('subsArea').append(sub);
  }
  $('trustTitle').textContent = checked ? 'Quality checked' : 'Recipe preview';
  $('trustDesc').textContent = checked ? (r.document_complete===false ? 'The Validator checked this recipe, but parts of the uploaded document were unreadable. Double-check ingredients and quantities.' : 'Your recipe passed the n8n Validator. Ingredient quantities and nutrition come from the recipe source.') : 'This is a preview. Run a live request to get a recipe reviewed by your AI Validator.';
  $('saveRecipe').classList.toggle('saved', !!savedRecipes.find(s => recipeKey(s) === recipeKey(r)));
  $('saveRecipe').textContent = savedRecipes.find(s => recipeKey(s) === recipeKey(r)) ? '♥ Saved' : '♡ Save recipe';
  $('startCooking').textContent = 'Start cooking ↗';
}
function fallbackArt(r) {
  const holder = make('div','fallback-food');
  holder.append(make('div','food-orb orb-1'),make('div','food-orb orb-2'));
  const circle=make('div','dish-circle'); const emoji=make('span');
  const name=norm(r.name);
  emoji.textContent = /(orange|lemon|juice|spritzer|citrus)/.test(name) ? '🍊' : /(salad|vegetable|broccoli)/.test(name) ? '🥗' : /(pasta|spaghetti|lasagna)/.test(name) ? '🍝' : /(soup|stew)/.test(name) ? '🥣' : /(cake|cookie|dessert)/.test(name) ? '🍰' : /(egg|omelette)/.test(name) ? '🍳' : '🍲';
  circle.append(emoji);holder.append(circle,make('span','fallback-scribble','made for you ✳'));return holder;
}
function renderIngredients(r) {
  const list=$('ingredientList');list.replaceChildren();const key='ticks.'+recipeKey(r);const ticked=new Set(safeStorage.get(key, []));
  function progress(){ const total=r.ingredients.length;const count=list.querySelectorAll('input:checked').length; $('ingredientProgress').textContent=`${count} / ${total}`; }
  r.ingredients.forEach((item,index)=>{
    const label=make('label','ingredient');const check=make('input');check.type='checkbox';check.checked=ticked.has(index);
    check.setAttribute('aria-label',`I have ${item}`);
    check.addEventListener('change',()=>{check.checked?ticked.add(index):ticked.delete(index);safeStorage.set(key,[...ticked]);progress();});
    label.append(check,make('span','',item));list.append(label);
  });progress();
  const missing=$('missingBanner');missing.hidden=!r.missing.length;
  missing.textContent=r.missing.length ? `Still to get (${r.missing.length}): ${r.missing.slice(0,10).join(', ')}${r.missing.length>10?'…':''}`:'';
  const have=$('pantryNote');have.hidden=!r.have.length;have.textContent=r.have.length ? `Already in your kitchen: ${r.have.join(', ')}`:'';
}
function renderSteps(r) {
  const list=$('stepsList');list.replaceChildren(); const key='steps.'+recipeKey(r);const done=new Set(safeStorage.get(key,[]));
  r.steps.forEach((step,i)=>{
    const btn=make('button','step');btn.type='button';btn.setAttribute('aria-pressed',String(done.has(i)));btn.classList.toggle('done',done.has(i));
    btn.style.textAlign='left';btn.style.width='100%';btn.style.backgroundColor='transparent';btn.style.border='0';
    btn.append(make('span','step-number',i+1),make('p','step-text',sentenceCase(step)));
    btn.addEventListener('click',()=>{done.has(i)?done.delete(i):done.add(i);safeStorage.set(key,[...done]);btn.classList.toggle('done',done.has(i));btn.setAttribute('aria-pressed',String(done.has(i)));if(done.size===r.steps.length&&r.steps.length)toast('Every step done. Nice cooking! ✳');});
    list.append(btn);
  });
  if(!r.steps.length)list.append(make('p','method-subtitle','No steps were detected in this recipe. Check your uploaded image or try another recipe.'));
}
function renderNutrition(r) {
  const calories=$('caloriesValue');calories.textContent=r.kcal != null ? r.kcal.toLocaleString(undefined,{maximumFractionDigits:1}) : '—';
  const rows=$('nutritionRows');rows.replaceChildren();
  [['Protein',r.protein_g],['Carbohydrates',r.carbs_g],['Fat',r.fat_g]].forEach(([name,n])=>{
    const row=make('div','nutrition-row');row.append(make('span','',name),make('strong','',n==null?'Not available':`${n} g`));rows.append(row);
  });
  $('caloriesBlock').hidden=r.kcal==null; $('nutritionRows').hidden=[r.protein_g,r.carbs_g,r.fat_g].every(n=>n==null);
  if(r.kcal==null && [r.protein_g,r.carbs_g,r.fat_g].every(n=>n==null)) rows.hidden=false;
  else rows.hidden=$('nutritionRows').hidden;
}
function plainRecipe(r,ingredientsOnly=false) {
  if(ingredientsOnly)return r.ingredients.map(x=>'- '+x).join('\n');
  return `${sentenceCase(r.name)}${r.minutes!=null?' • '+r.minutes+' min':''}\n\nINGREDIENTS\n${r.ingredients.map(x=>'- '+x).join('\n')}\n\nSTEPS\n${r.steps.map((x,i)=>(i+1)+'. '+sentenceCase(x)).join('\n')}\n${r.chef_note?'\nCHEF NOTE\n'+r.chef_note+'\n':''}`;
}
async function copy(value) { try {await navigator.clipboard.writeText(value);toast('Copied to clipboard.');}catch{const t=document.createElement('textarea');t.value=value;document.body.append(t);t.select();try{document.execCommand('copy');toast('Copied to clipboard.')}catch{toast('Copy not supported in this browser.',true)}t.remove();} }
function toggleSave() {
  if(!recipe)return;
  const key=recipeKey(recipe);const found=savedRecipes.findIndex(s=>recipeKey(s)===key);
  if(found>=0){savedRecipes.splice(found,1);toast('Removed from saved recipes.')} else{savedRecipes.unshift(recipe);savedRecipes=savedRecipes.slice(0,30);toast('Saved to your kitchen collection.');}
  safeStorage.set('saved',savedRecipes);updateSavedCount();
  $('saveRecipe').textContent=found>=0?'♡ Save recipe':'♥ Saved';$('saveRecipe').classList.toggle('saved',found<0);
}
function openDrawer(title) {
  lastFocus=document.activeElement;
  $('drawerTitle').textContent=title;
  $('drawerBackdrop').hidden=false;$('drawer').hidden=false;document.body.classList.add('drawer-open');
  $('closeDrawer').focus();
}
function closeDrawer(){ $('drawerBackdrop').hidden=true;$('drawer').hidden=true;document.body.classList.remove('drawer-open');if(lastFocus?.focus)lastFocus.focus(); }
function openSettings() {
  openDrawer('Make it yours.');const content=$('drawerContent');content.replaceChildren();
  content.append(make('p','drawer-section-intro','Connect this interface to your existing recipe-helper n8n webhook. The URL stays in your browser.'));
  const label=make('label','','n8n webhook URL'); const input=make('input');input.type='url';input.autocomplete='url';input.value=safeStorage.get('endpoint',DEFAULT_ENDPOINT);input.placeholder=DEFAULT_ENDPOINT;label.append(input);content.append(label);
  const hint=make('p','drawer-note','Use /webhook/recipe-helper for an active workflow, or /webhook-test/recipe-helper while listening for a test event. If this site and n8n use different origins, configure CORS or a reverse proxy.');content.append(hint);
  const btn=make('button','drawer-primary','Save connection');btn.type='button';btn.onclick=()=>{if(!/^https?:\/\//i.test(input.value) && !input.value.startsWith('/')){toast('Enter an http(s) URL or a same-origin path.',true);return;}safeStorage.set('endpoint',trim(input.value));closeDrawer();toast('Webhook connection saved.');};content.append(btn);
  content.append(make('p','drawer-note','Privacy note: image uploads and text are sent to the webhook you configure. Avoid using public production endpoints without appropriate server-side protection.'));
}
function openSaved() {
  openDrawer('Recipes worth keeping.');const content=$('drawerContent');content.replaceChildren();
  content.append(make('p','drawer-section-intro',savedRecipes.length?'Saved in this browser, ready whenever inspiration strikes.':'Your saved recipes will show up here. Find one you love and tap Save recipe.'));
  savedRecipes.forEach(r=>{
    const item=make('div','saved-item'); const info=make('div');info.append(make('strong','',r.name),make('span','',r.minutes!=null?`${r.minutes} min · recipe`:'Your saved recipe'));
    const open=make('button','','View ↗');open.type='button';open.onclick=()=>{recipe=r;renderRecipe(r);$('recipeResult').hidden=false;closeDrawer();$('recipeResult').scrollIntoView({behavior:'smooth'});};item.append(info,open);content.append(item);
  });
}
function openPantry() {
  openDrawer('The good stuff you have.');const content=$('drawerContent');content.replaceChildren();
  content.append(make('p','drawer-section-intro','Keep a little list of the ingredients you have. Use it to start a recipe search in one tap.'));
  const row=make('div','drawer-add-row');const input=make('input');input.type='text';input.maxLength=70;input.placeholder='e.g. chickpeas';input.setAttribute('aria-label','Add pantry ingredient');const add=make('button','','Add');row.append(input,add);content.append(row);
  const chips=make('div','pantry-chip-list');content.append(chips);
  function redraw(){chips.replaceChildren();pantry.forEach((name,index)=>{const chip=make('div','pantry-chip');chip.append(make('span','',name));const remove=make('button','','×');remove.type='button';remove.setAttribute('aria-label',`Remove ${name}`);remove.onclick=()=>{pantry.splice(index,1);safeStorage.set('pantry',pantry);redraw();};chip.append(remove);chips.append(chip);});}
  function addItem(){const item=trim(input.value,70).replace(/[,;]+/g,'');if(!item)return;if(!pantry.some(v=>norm(v)===norm(item))){pantry.push(item);safeStorage.set('pantry',pantry);redraw();}input.value='';input.focus();}
  add.onclick=addItem;input.onkeydown=e=>{if(e.key==='Enter')addItem();};redraw();
  const use=make('button','drawer-primary','Find recipes with my pantry ↗');use.onclick=()=>{if(!pantry.length){toast('Add an ingredient first.',true);return;}$('recipeQuery').value='I have '+pantry.join(', ');closeDrawer();$('search').scrollIntoView({behavior:'smooth'});$('recipeQuery').focus();};content.append(use);
}
function openCooking() {
  if(!recipe)return;
  if(!recipe.steps.length){toast('This recipe has no steps to follow.',true);return;}
  cookingStep=0;openDrawer('One step at a time.');renderCookingStep();
}
function renderCookingStep() {
  const content=$('drawerContent');content.replaceChildren();
  content.append(make('p','drawer-section-intro',`${recipe.name} · Step ${cookingStep+1} of ${recipe.steps.length}`));
  const bar=make('div');bar.style.cssText='height:7px;background:#e1e8dc;border-radius:99px;overflow:hidden;margin:22px 0 35px';
  const fill=make('div');fill.style.cssText=`height:100%;width:${100*(cookingStep+1)/recipe.steps.length}%;background:#658f6e;border-radius:99px;transition:width .25s`;bar.append(fill);content.append(bar);
  const step=make('p','',sentenceCase(recipe.steps[cookingStep]));step.style.cssText='font:400 29px/1.45 Georgia,serif;letter-spacing:-.7px;color:#31533c;margin-bottom:50px';content.append(step);
  const row=make('div','drawer-add-row'); const previous=make('button','','← Back');const next=make('button','',cookingStep===recipe.steps.length-1?'Finish ✓':'Next step →');previous.disabled=cookingStep===0;
  previous.onclick=()=>{cookingStep--;renderCookingStep();};next.onclick=()=>{if(cookingStep===recipe.steps.length-1){closeDrawer();toast('You did it. Time to enjoy your dish!');}else{cookingStep++;renderCookingStep();}};
  row.append(previous,next);content.append(row);
  content.append(make('p','drawer-note','Cooking view keeps one step on screen at a time, so you can focus on your food.'));
}
function addPhoto(file) {
  if(!file)return;
  if(!['image/jpeg','image/png','image/webp'].includes(file.type)){showMessage('Please choose a JPG, PNG, or WebP image.');return;}
  if(file.size>12_000_000){showMessage('That photo is too large (maximum 12 MB). Try a smaller file.');return;}
  if(photoPreviewUrl)URL.revokeObjectURL(photoPreviewUrl);
  photoFile=file;photoPreviewUrl=URL.createObjectURL(file);$('previewImage').src=photoPreviewUrl;$('imageName').textContent=file.name;$('uploadPreview').hidden=false;showMessage('');
}
function clearPhoto(){photoFile=null;$('imageFile').value='';$('uploadPreview').hidden=true;if(photoPreviewUrl)URL.revokeObjectURL(photoPreviewUrl);photoPreviewUrl='';}
function showDemo(){recipe=normalizeRecipe(demoRecipe);renderRecipe(recipe);$('recipeResult').hidden=false;$('recipeResult').scrollIntoView({behavior:'smooth'});}
function openMenu() {
  openDrawer('The kitchen menu.');
  const content=$('drawerContent');content.replaceChildren();
  content.append(make('p','drawer-section-intro','All your favorite kitchen tools, one tap away.'));
  [['My pantry',openPantry],['Saved recipes',openSaved],['Webhook settings',openSettings]].forEach(([name,fn])=>{
    const btn=make('button','drawer-primary',name+' ↗');btn.onclick=fn;content.append(btn);
  });
}
// Event hooks
$('mobileMenu').addEventListener('click',openMenu);
const dropTarget=document.querySelector('.search-card');
dropTarget.addEventListener('dragover',e=>{if(e.dataTransfer?.types?.includes('Files')){e.preventDefault();dropTarget.classList.add('drag-over');}});
dropTarget.addEventListener('dragleave',e=>{if(!dropTarget.contains(e.relatedTarget))dropTarget.classList.remove('drag-over');});
dropTarget.addEventListener('drop',e=>{e.preventDefault();dropTarget.classList.remove('drag-over');if(e.dataTransfer?.files?.[0])addPhoto(e.dataTransfer.files[0]);});
$('searchSubmit').addEventListener('click', submitRequest);
$('recipeQuery').addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){e.preventDefault();submitRequest();}});
$('imageFile').addEventListener('change',e=>addPhoto(e.target.files[0]));
$('removeImage').addEventListener('click',clearPhoto);
$('filterToggle').addEventListener('click',()=>{const open=$('filterPanel').hidden;$('filterPanel').hidden=!open;$('filterToggle').setAttribute('aria-expanded',String(open));});
document.querySelectorAll('[data-query]').forEach(btn=>btn.addEventListener('click',()=>{$('recipeQuery').value=btn.dataset.query;$('recipeQuery').focus();$('search').scrollIntoView({behavior:'smooth'});}));
$('viewDemo').addEventListener('click',showDemo);
$('cancelBtn').addEventListener('click',()=>{if(activeController)activeController.abort('cancelled');});
$('newSearch').addEventListener('click',()=>{$('search').scrollIntoView({behavior:'smooth'});$('recipeQuery').focus();});
$('saveRecipe').addEventListener('click',toggleSave);
$('copyRecipe').addEventListener('click',()=>{if(recipe)copy(plainRecipe(recipe));});
$('copyIngredients').addEventListener('click',()=>{if(recipe)copy(plainRecipe(recipe,true));});
$('printRecipe').addEventListener('click',()=>window.print());
$('startCooking').addEventListener('click',openCooking);
$('settingsBtn').addEventListener('click',openSettings);
$('savedNav').addEventListener('click',openSaved);
$('pantryNav').addEventListener('click',openPantry);
$('closeDrawer').addEventListener('click',closeDrawer);$('drawerBackdrop').addEventListener('click',closeDrawer);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('drawer').hidden)closeDrawer();});
updateSavedCount();
if(new URLSearchParams(location.search).has('demo'))window.addEventListener('load',()=>setTimeout(showDemo,130));
