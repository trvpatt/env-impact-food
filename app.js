const pages = {
  learn: { element: document.querySelector("#learn-page"), title: "Explore" },
  restaurants: { element: document.querySelector("#restaurants-page"), title: "Restaurants" },
  recipes: { element: document.querySelector("#recipes-page"), title: "Recipes" }
};

const previewPanel = document.querySelector("#preview-panel");
const previewContent = document.querySelector("#preview-content");
const recipesStatus = document.querySelector("#recipes-status");
const restaurantsStatus = document.querySelector("#places-status");
const recipeResults = document.querySelector("#recipe-results");
const restaurantResults = document.querySelector("#restaurant-results");
let selectedDiet = "vegetarian";
let selectedCuisine = "Thai";
let selectedRestaurantDiet = "vegetarian";
let toastTimeout;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function setPage(name) {
  if (!pages[name]) return;
  Object.entries(pages).forEach(([key, page]) => {
    const active = key === name;
    page.element.hidden = !active;
    page.element.classList.toggle("active", active);
  });
  document.querySelectorAll(".nav-link").forEach((button) => {
    const active = button.dataset.page === name;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  document.querySelector("#page-breadcrumb").textContent = pages[name].title;
  closePreview();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(toastTimeout);
  toastTimeout = window.setTimeout(() => toast.classList.remove("show"), 2800);
}

function openPreview(markup) {
  previewContent.innerHTML = markup;
  previewPanel.classList.add("open");
  previewPanel.setAttribute("aria-hidden", "false");
  document.body.classList.add("preview-open");
  document.querySelector("#close-preview").focus();
}

function closePreview() {
  previewPanel.classList.remove("open");
  previewPanel.setAttribute("aria-hidden", "true");
  document.body.classList.remove("preview-open");
}

function sourcePreview() {
  openPreview(`
    <p class="preview-kicker">OUR SOURCES &amp; APPROACH</p>
    <h2>Good information, without the overclaiming.</h2>
    <p>The comparison on this page is based on global food-production averages from Poore &amp; Nemecek (2018), published by Our World in Data. It is directional context, not a personal prediction.</p>
    <div class="preview-meta"><span>Global averages</span><span>Per kilogram</span></div>
    <hr class="preview-divider">
    <p>The environmental impact score combines greenhouse gas emissions, land use, eutrophying emissions, and scarcity-weighted water use. Results can vary by farm, region, production method, and food choice.</p>
    <p>The values shown in the chart are greenhouse gas emissions: peas <strong>0.98 kg CO₂e/kg</strong> and beef (beef herd) <strong>99.48 kg CO₂e/kg</strong>.</p>
    <div class="preview-actions"><a class="button button-dark" href="https://ourworldindata.org/environmental-impacts-of-food" target="_blank" rel="noopener noreferrer">Read the source ↗</a></div>
  `);
}

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function getPlacesErrorMessage(error) {
  if (window.location.protocol === "file:") {
    return "This page was opened as a file. Start the backend and open http://localhost:8000 (see README) to use Google Places.";
  }
  if (error instanceof TypeError) {
    return "Can't reach the restaurant search backend. Start it with the README instructions and open this app at http://localhost:8000.";
  }
  return error.message || "Nearby places could not be loaded.";
}

function safeExternalUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function openRestaurant(place) {
  const mapsUrl = safeExternalUrl(place.googleMapsUri);
  const websiteUrl = safeExternalUrl(place.websiteUri);
  const name = place.name || "Restaurant";
  const rating = place.rating ? `${place.rating.toFixed(1)} ★${place.userRatingCount ? ` · ${place.userRatingCount.toLocaleString()} reviews` : ""}` : null;
  openPreview(`
    <p class="preview-kicker">NEARBY PLACE · GOOGLE MAPS</p>
    <h2>${escapeHtml(name)}</h2>
    <div class="preview-meta"><span>Plant-friendly search match</span>${rating ? `<span>${escapeHtml(rating)}</span>` : ""}</div>
    <p>${place.address ? escapeHtml(place.address) : "Address not listed."}</p>
    <p>Search result matched “${selectedRestaurantDiet} restaurants.” Check the restaurant’s menu for current dietary options.</p>
    <div class="preview-actions">
      ${mapsUrl ? `<a class="button button-dark" href="${escapeHtml(mapsUrl)}" target="_blank" rel="noopener noreferrer">View in Google Maps ↗</a>` : ""}
      ${websiteUrl ? `<a class="button button-light" href="${escapeHtml(websiteUrl)}" target="_blank" rel="noopener noreferrer">Restaurant website ↗</a>` : ""}
    </div>
    <hr class="preview-divider">
    <p class="frame-note">Place information provided by Google Maps Platform.</p>
  `);
}

const meatTerms = /\b(beef|pork|ham|bacon|lamb|mutton|chicken|turkey|duck|fish|salmon|tuna|shrimps?|prawns?|crabs?|lobsters?|anchov(?:y|ies)|chorizo|sausages?|salami|prosciutto|pepperoni|pancetta|frankfurters?|hot dogs?|squid|calamari|mussels?|clams?|scallops?|oysters?|gelatin|gelatine|lard|suet|oyster sauce|fish sauce|worcestershire)\b/i;
const animalProductTerms = /\b(milk|cream|butter|cheese|yogurt|yoghurt|ghee|egg|honey|whey|casein|mayonnaise|mayonaise|gelatin|gelatine|dairy|parmesan|ricotta|mozzarella|paneer)\b/i;
const plantMilkTerms = /\b(almond|coconut|oat|soy|soya|rice|cashew|hemp|pea|hazelnut) milk\b/i;

function ingredientNames(meal) {
  const ingredients = [];
  for (let index = 1; index <= 20; index += 1) {
    const name = meal[`strIngredient${index}`]?.trim();
    if (name) ingredients.push(name.toLowerCase());
  }
  return ingredients;
}

function fitsDiet(meal, diet) {
  const ingredients = ingredientNames(meal);
  const listed = [meal.strMeal || "", ...ingredients].join(" ");
  if (!ingredients.length || meatTerms.test(listed)) return false;
  return diet !== "vegan" || !ingredients.some((ingredient) =>
    animalProductTerms.test(ingredient) && !plantMilkTerms.test(ingredient)
  );
}

async function fetchMealDetails(meals) {
  const ids = [...new Set(meals.map((meal) => meal.idMeal).filter(Boolean))].slice(0, 30);
  const responses = await Promise.all(ids.map(async (id) => {
    const response = await fetch(`https://www.themealdb.com/api/json/v1/1/lookup.php?i=${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error("Recipe details could not be loaded.");
    const data = await response.json();
    return data.meals?.[0] || null;
  }));
  return responses.filter(Boolean);
}

function renderRecipes(meals, options = {}) {
  recipeResults.replaceChildren();
  if (!meals.length) {
    setStatus(recipesStatus, options.emptyMessage || "No recipes matched those filters. Try another cuisine or a different ingredient.", true);
    return;
  }
  setStatus(recipesStatus, `${meals.length} recipe${meals.length === 1 ? "" : "s"} found. Select one to open its source.`);
  meals.forEach((meal) => {
    const url = safeExternalUrl(meal.url);
    if (!url) {
      setStatus(recipesStatus, `“${meal.name}” does not have a valid recipe link and was skipped.`, true);
      return;
    }
    const card = document.createElement("a");
    card.className = "recipe-card";
    card.href = url;
    card.setAttribute("aria-label", `Open recipe: ${meal.name}`);
    const image = safeExternalUrl(meal.image);
    card.innerHTML = `
      ${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy">` : `<div class="recipe-card-image-placeholder"></div>`}
      <div class="recipe-card-body">
        <h3 class="recipe-card-title">${escapeHtml(meal.name)}</h3>
        <div class="recipe-card-footer"><span>${escapeHtml(meal.area || meal.cuisine || "Plant-forward")}</span><span>${meal.matchCount ? `${meal.matchCount} match${meal.matchCount === 1 ? "" : "es"} · ` : ""}Open recipe ↗</span></div>
      </div>`;
    recipeResults.append(card);
  });
}

async function browseCuisine() {
  const button = document.querySelector("#browse-recipes-button");
  button.disabled = true;
  button.innerHTML = "Finding recipes <span aria-hidden=\"true\">…</span>";
  recipeResults.replaceChildren();
  document.querySelector("#recipes-results-title").textContent = `${selectedDiet === "vegan" ? "Vegan" : "Vegetarian"} ${selectedCuisine} ideas`;
  setStatus(recipesStatus, `Searching ${selectedCuisine} recipes and checking listed ingredients…`);
  try {
    const response = await fetch(`https://www.themealdb.com/api/json/v1/1/filter.php?a=${encodeURIComponent(selectedCuisine)}`);
    if (!response.ok) throw new Error("The recipe service could not be reached. Please try again.");
    const data = await response.json();
    if (!data.meals?.length) {
      renderRecipes([], { emptyMessage: `No ${selectedCuisine} recipes were returned. Try another cuisine.` });
      return;
    }
    const details = await fetchMealDetails(data.meals);
    const compatible = details.filter((meal) => fitsDiet(meal, selectedDiet)).slice(0, 9);
    renderRecipes(compatible.map((meal) => ({
      name: meal.strMeal,
      image: meal.strMealThumb,
      url: meal.strSource || `https://www.themealdb.com/meal/${meal.idMeal}`,
      area: meal.strArea || selectedCuisine,
      cuisine: selectedCuisine,
      diet: `${selectedDiet === "vegan" ? "Vegan" : "Vegetarian"} match`
    })));
  } catch (error) {
    setStatus(recipesStatus, `${error.message || "Recipes could not be loaded."} Check your connection and try again.`, true);
  } finally {
    button.disabled = false;
    button.innerHTML = "Find recipes <span aria-hidden=\"true\">→</span>";
  }
}

function normalizeIngredient(value) {
  return value.trim().toLowerCase().replace(/[^a-z0-9 -]/g, "").replace(/\s+/g, " ");
}

async function findRecipesByIngredients(event) {
  event.preventDefault();
  const input = document.querySelector("#ingredients-input");
  const ingredients = [...new Set(input.value.split(",").map(normalizeIngredient).filter(Boolean))].slice(0, 5);
  if (!ingredients.length) {
    input.focus();
    showToast("Add at least one ingredient to search.");
    return;
  }
  input.value = ingredients.join(", ");
  document.querySelector("#recipes-results-title").textContent = "Recipes from your ingredients";
  recipeResults.replaceChildren();
  setStatus(recipesStatus, `Matching ${ingredients.join(", ")} against recipe ingredients…`);
  try {
    const lists = await Promise.all(ingredients.map(async (ingredient) => {
      const response = await fetch(`https://www.themealdb.com/api/json/v1/1/filter.php?i=${encodeURIComponent(ingredient)}`);
      if (!response.ok) throw new Error(`Could not search for “${ingredient}”.`);
      const data = await response.json();
      return (data.meals || []).map((meal) => meal.idMeal);
    }));
    const counts = new Map();
    lists.forEach((ids) => ids.forEach((id) => counts.set(id, (counts.get(id) || 0) + 1)));
    const rankedIds = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 15);
    if (!rankedIds.length) {
      renderRecipes([], { emptyMessage: "No matches found. Try broader ingredient names, such as “bean” instead of a specific brand." });
      return;
    }
    const idSet = new Set(rankedIds.map(([id]) => id));
    const details = await fetchMealDetails(rankedIds.map(([id]) => ({ idMeal: id })));
    const matches = details
      .filter((meal) => idSet.has(meal.idMeal) && fitsDiet(meal, selectedDiet))
      .map((meal) => {
        const found = ingredients.filter((ingredient) =>
          ingredientNames(meal).some((name) => name.includes(ingredient) || ingredient.includes(name))
        );
        return {
          name: meal.strMeal,
          image: meal.strMealThumb,
          url: meal.strSource || `https://www.themealdb.com/meal/${meal.idMeal}`,
          area: meal.strArea,
          matchCount: found.length,
          matchedIngredients: found,
          diet: `${selectedDiet === "vegan" ? "Vegan" : "Vegetarian"} match`
        };
      })
      .sort((a, b) => b.matchCount - a.matchCount)
      .slice(0, 9);
    renderRecipes(matches, { emptyMessage: "We found recipes, but none passed the selected dietary ingredient check. Try switching to vegetarian or using other ingredients." });
  } catch (error) {
    setStatus(recipesStatus, `${error.message || "Ingredient search failed."} Check your connection and try again.`, true);
  }
}

function haversineDistance(lat1, lon1, lat2, lon2) {
  const radians = (degrees) => degrees * Math.PI / 180;
  const deltaLat = radians(lat2 - lat1);
  const deltaLon = radians(lon2 - lon1);
  const value = Math.sin(deltaLat / 2) ** 2 +
    Math.cos(radians(lat1)) * Math.cos(radians(lat2)) * Math.sin(deltaLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

async function searchNearbyPlaces(search, locationLabel) {
  restaurantResults.replaceChildren();
  setStatus(restaurantsStatus, `Searching for ${selectedRestaurantDiet} restaurants near ${locationLabel}…`);
  try {
    if (window.location.protocol === "file:") throw new Error("Restaurant search needs the backend server.");
    const response = await fetch("/api/places/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...search, diet: selectedRestaurantDiet })
    });
    if (!response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("The restaurant search backend isn't responding. Start it with the README instructions and open this app at http://localhost:8000.");
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The nearby places service is temporarily unavailable.");
    const uniquePlaces = [...new Map((result.places || []).map((place) => [place.id, place])).values()];
    document.querySelector("#places-heading").textContent = uniquePlaces.length ? `Plant-friendly places near ${locationLabel}.` : "No nearby matches yet.";
    document.querySelector("#places-meta").textContent = `${uniquePlaces.length} Google Maps result${uniquePlaces.length === 1 ? "" : "s"}`;
    if (!uniquePlaces.length) {
      setStatus(restaurantsStatus, `No ${selectedRestaurantDiet} restaurant matches were found near ${locationLabel}. Try a nearby area or broader search term.`, true);
    } else {
      setStatus(restaurantsStatus, `${uniquePlaces.length} restaurant result${uniquePlaces.length === 1 ? "" : "s"} for ${selectedRestaurantDiet} restaurants near ${locationLabel}. Select one for details.`);
      uniquePlaces.forEach((place) => {
        const card = document.createElement("article");
        card.className = "restaurant-card";
        const name = place.name || "Restaurant";
        const rating = place.rating ? `${Number(place.rating).toFixed(1)} ★${place.userRatingCount ? ` (${Number(place.userRatingCount).toLocaleString()})` : ""}` : "";
        card.innerHTML = `
          <span class="restaurant-icon" aria-hidden="true">✳</span>
          <div class="restaurant-info">
            <strong>${escapeHtml(name)}</strong>
            <div class="restaurant-details">
              <span class="tag">${escapeHtml(selectedRestaurantDiet === "vegan" ? "Vegan search" : "Vegetarian search")}</span>
              ${place.primaryType ? `<span>${escapeHtml(place.primaryType)}</span>` : ""}
              ${place.address ? `<span>${escapeHtml(place.address)}</span>` : ""}
            </div>
          </div>
          ${rating ? `<span class="restaurant-distance">${escapeHtml(rating)}</span>` : ""}
          <button class="icon-button" type="button" aria-label="Preview ${escapeHtml(name)}">↗</button>`;
        card.addEventListener("click", () => openRestaurant(place));
        restaurantResults.append(card);
      });
    }
  } catch (error) {
    setStatus(restaurantsStatus, getPlacesErrorMessage(error), true);
  }
}

async function findPlacesByArea(event) {
  event.preventDefault();
  const input = document.querySelector("#area-search-input");
  const area = input.value.trim();
  if (!area) {
    input.focus();
    return;
  }
  const button = document.querySelector("#area-search-form button");
  button.disabled = true;
  button.innerHTML = "Searching area <span aria-hidden=\"true\">…</span>";
  setStatus(restaurantsStatus, `Searching for ${selectedRestaurantDiet} restaurants in ${area}…`);
  try {
    document.querySelector("#places-meta").textContent = `Search area: ${area}`;
    await searchNearbyPlaces({ area }, area);
  } catch (error) {
    setStatus(restaurantsStatus, getPlacesErrorMessage(error), true);
  } finally {
    button.disabled = false;
    button.innerHTML = "Search area <span aria-hidden=\"true\">→</span>";
  }
}

function findNearbyPlaces() {
  const button = document.querySelector("#find-places-button");
  restaurantResults.replaceChildren();
  if (!navigator.geolocation) {
    setStatus(restaurantsStatus, "This browser doesn't provide location access. Search by city or ZIP below instead.", true);
    return;
  }
  if (!window.isSecureContext) {
    setStatus(restaurantsStatus, "Browser location requires a secure page. Open this site on localhost or HTTPS, or search by city or ZIP below.", true);
    return;
  }
  button.disabled = true;
  button.innerHTML = "Finding nearby places <span aria-hidden=\"true\">…</span>";
  setStatus(restaurantsStatus, "Requesting your location… If this takes too long, search by city or ZIP below.");
  navigator.geolocation.getCurrentPosition(async (position) => {
    const { latitude, longitude } = position.coords;
    document.querySelector("#places-meta").textContent = "Location is only used for this search";
    await searchNearbyPlaces({ latitude, longitude }, "your location");
    button.disabled = false;
    button.innerHTML = "Use my location <span aria-hidden=\"true\">→</span>";
  }, (error) => {
    const message = error.code === error.PERMISSION_DENIED
      ? "Location access was denied. Allow it in your browser or device settings, or search by city or ZIP below."
      : error.code === error.POSITION_UNAVAILABLE
        ? "Your device couldn't determine your location. Check device location services, or search by city or ZIP below."
        : "Your location didn't arrive in time. Try again, check device location services, or search by city or ZIP below.";
    setStatus(restaurantsStatus, message, true);
    button.disabled = false;
    button.innerHTML = "Use my location <span aria-hidden=\"true\">→</span>";
  }, { enableHighAccuracy: false, timeout: 45000, maximumAge: 600000 });
}

document.querySelectorAll("[data-page]").forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.page));
});
document.querySelectorAll("[data-open-page]").forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.openPage));
});
document.querySelector("#methodology-button").addEventListener("click", sourcePreview);
document.querySelectorAll("[data-open-methodology]").forEach((button) => button.addEventListener("click", sourcePreview));
document.querySelector("#close-preview").addEventListener("click", closePreview);
document.querySelector("#sidebar-toggle").addEventListener("click", (event) => {
  const button = event.currentTarget;
  const collapsed = document.body.classList.toggle("sidebar-collapsed");
  button.setAttribute("aria-expanded", String(!collapsed));
  button.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
  button.setAttribute("title", collapsed ? "Expand navigation" : "Collapse navigation");
  button.querySelector("span").textContent = collapsed ? "›" : "‹";
});
document.querySelector("#find-places-button").addEventListener("click", findNearbyPlaces);
document.querySelector("#area-search-form").addEventListener("submit", findPlacesByArea);
document.querySelector("#browse-recipes-button").addEventListener("click", browseCuisine);
document.querySelector("#ingredients-form").addEventListener("submit", findRecipesByIngredients);
document.querySelectorAll("[data-diet]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedDiet = button.dataset.diet;
    document.querySelectorAll("[data-diet]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  });
});
document.querySelectorAll("[data-restaurant-diet]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedRestaurantDiet = button.dataset.restaurantDiet;
    document.querySelectorAll("[data-restaurant-diet]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  });
});
document.querySelectorAll("[data-cuisine]").forEach((button) => {
  button.addEventListener("click", () => {
    selectedCuisine = button.dataset.cuisine;
    document.querySelectorAll("[data-cuisine]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && previewPanel.classList.contains("open")) closePreview();
});
