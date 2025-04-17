<script lang="ts">
	import { onMount, getContext, tick } from 'svelte';
	import { models, tools, functions, knowledge as knowledgeCollections, user } from '$lib/stores';

	import AdvancedParams from '$lib/components/chat/Settings/Advanced/AdvancedParams.svelte';
	import Tags from '$lib/components/common/Tags.svelte';
	import Knowledge from '$lib/components/workspace/Models/Knowledge.svelte';
	import ToolsSelector from '$lib/components/workspace/Models/ToolsSelector.svelte';
	import FiltersSelector from '$lib/components/workspace/Models/FiltersSelector.svelte';
	import ActionsSelector from '$lib/components/workspace/Models/ActionsSelector.svelte';
	import Capabilities from '$lib/components/workspace/Models/Capabilities.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte'; // Assuming this component handles its own styling and rows
	import { getTools } from '$lib/apis/tools';
	import { getFunctions } from '$lib/apis/functions';
	import { getKnowledgeBases } from '$lib/apis/knowledge';
	import AccessControl from '../common/AccessControl.svelte';
	import { stringify } from 'postcss';
	import { toast } from 'svelte-sonner';
	// Removed incorrect Input import
	import Plus from '$lib/components/icons/Plus.svelte'; // Added import
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte'; // Added import

	const i18n = getContext('i18n');

	export let onSubmit: Function;
	export let onBack: null | Function = null;

	export let model = null;
	export let edit = false;

	export let preset = true;

	let loading = false;
	let success = false;

	let filesInputElement;
	let inputFiles;

	let showAdvanced = false;
	let showPreview = false;

	let loaded = false;

	// ///////////
	// model
	// ///////////

	let id = '';
	let name = '';

	let enableDescription = true;

	$: if (!edit) {
		if (name) {
			id = name
				.replace(/\s+/g, '-')
				.replace(/[^a-zA-Z0-9-]/g, '')
				.toLowerCase();
		}
	}

	let info = {
		id: '',
		base_model_id: null,
		name: '',
		meta: {
			profile_image_url: '/static/favicon.png',
			description: '',
			suggestion_prompts: null,
			tags: []
		},
		params: {
			system: ''
			// custom_roles will be added dynamically if needed
		}
	};

	let params = {
		system: ''
	};
	let capabilities = {
		vision: true,
		usage: undefined,
		citations: true
	};

	let knowledge = [];
	let toolIds = [];
	let filterIds = [];
	let actionIds = [];

	let accessControl = {};

	// Added customRoles state variable
	let customRoles = [];

	// Added initialization logic for customRoles
	// Initialize customRoles and ensure params exist
	$: {
		if (info && info.params) {
			// Ensure custom_roles exists
			if (!info.params.custom_roles) {
				info.params.custom_roles = [];
			}
			// Use the array from info.params directly
			customRoles = info.params.custom_roles;
		} else if (info && !info.params) {
			// Initialize params if it doesn't exist
			info.params = { system: '', custom_roles: [] }; // Initialize system prompt as well
			customRoles = info.params.custom_roles;
		} else {
			// Fallback if info is null/undefined initially
			customRoles = [];
		}
	}


	const addUsage = (base_model_id) => {
		const baseModel = $models.find((m) => m.id === base_model_id);

		if (baseModel) {
			if (baseModel.owned_by === 'openai') {
				capabilities.usage = baseModel?.meta?.capabilities?.usage ?? false;
			} else {
				delete capabilities.usage;
			}
			capabilities = capabilities;
		}
	};

	const submitHandler = async () => {
		loading = true;

		info.id = id;
		info.name = name;

		if (id === '') {
			toast.error('Model ID is required.');
			loading = false; // Stop if validation fails
			return;
		}

		if (name === '') {
			toast.error('Model Name is required.');
			loading = false; // Stop if validation fails
			return;
		}

		// Ensure meta exists before assigning properties
        if (!info.meta) info.meta = {};
		info.access_control = accessControl;
		info.meta.capabilities = capabilities;

		if (enableDescription) {
			info.meta.description = info.meta.description?.trim() === '' ? null : info.meta.description;
		} else {
			info.meta.description = null;
		}

		if (knowledge.length > 0) {
			info.meta.knowledge = knowledge;
		} else {
			if (info.meta?.knowledge) { // Check meta exists
				delete info.meta.knowledge;
			}
		}

		if (toolIds.length > 0) {
			info.meta.toolIds = toolIds;
		} else {
			if (info.meta?.toolIds) { // Check meta exists
				delete info.meta.toolIds;
			}
		}

		if (filterIds.length > 0) {
			info.meta.filterIds = filterIds;
		} else {
			if (info.meta?.filterIds) { // Check meta exists
				delete info.meta.filterIds;
			}
		}

		if (actionIds.length > 0) {
			info.meta.actionIds = actionIds;
		} else {
			if (info.meta?.actionIds) { // Check meta exists
				delete info.meta.actionIds;
			}
		}

		// Ensure params exists before accessing stop
		if (!info.params) info.params = {};
		info.params.stop = params.stop ? params.stop.split(',').filter((s) => s.trim()) : null;

		// Process custom roles before finalizing params (Added Block)
		if (info.params.custom_roles) {
			info.params.custom_roles = info.params.custom_roles.filter(
				(role) => role.role.trim() !== '' || role.value.trim() !== ''
			);
		  // If after filtering the array is empty, delete the key
		  if (info.params.custom_roles.length === 0) {
			delete info.params.custom_roles;
		  }
		}
		// End of Added Block for custom roles processing

		// Ensure params exists before iterating
		if (info.params) {
			Object.keys(info.params).forEach((key) => {
				// Check if the value is null or an empty string
				if (info.params[key] === '' || info.params[key] === null) {
					// Special check for custom_roles: only delete if it doesn't exist after filtering
					if (key !== 'custom_roles' || !info.params.hasOwnProperty('custom_roles')) {
						delete info.params[key];
					}
				}
			});
		}


		try {
			await onSubmit(info);
			success = true; // Assume success if onSubmit doesn't throw
		} catch (error) {
			console.error("Submission error:", error);
			toast.error("Failed to save model."); // Provide feedback on error
			success = false;
		} finally {
			loading = false;
		}

	};

	// Added helper functions for custom roles
	const addCustomRole = () => {
		// Directly modify the array bound to the info object's params
	  if (!info.params) info.params = {}; // Ensure params exists
	  if (!info.params.custom_roles) {
			info.params.custom_roles = [];
	  }
		info.params.custom_roles = [...info.params.custom_roles, { role: '', value: '' }];
		customRoles = info.params.custom_roles; // Ensure local variable syncs
	};

	const deleteCustomRole = (index) => {
	  // Ensure params and custom_roles exist
	  if (info.params?.custom_roles) {
			info.params.custom_roles.splice(index, 1);
			info.params.custom_roles = info.params.custom_roles; // Trigger reactivity
		customRoles = info.params.custom_roles; // Ensure local variable syncs
	  }
	};
	// End of added helper functions

	onMount(async () => {
		await tools.set(await getTools(localStorage.token));
		await functions.set(await getFunctions(localStorage.token));
		await knowledgeCollections.set(await getKnowledgeBases(localStorage.token));

		// Scroll to top 'workspace-container' element
		const workspaceContainer = document.getElementById('workspace-container');
		if (workspaceContainer) {
			workspaceContainer.scrollTop = 0;
		}

		if (model) {
			name = model.name;
			await tick();

			id = model.id;

			enableDescription = model?.meta?.description !== null && model?.meta?.description !== undefined ;

			if (model.base_model_id) {
				const base_model = $models
					.filter((m) => !m?.preset && !(m?.arena ?? false))
					.find((m) => [model.base_model_id, `${model.base_model_id}:latest`].includes(m.id));

				console.log('base_model', base_model);

				if (base_model) {
					model.base_model_id = base_model.id;
				} else {
					model.base_model_id = null;
				}
			}


			// Deep clone the model to avoid modifying the original store object directly
			// This is crucial if `model` comes from a reactive store
			info = JSON.parse(JSON.stringify(model));

			// Ensure info.params exists after cloning
			if (!info.params) {
				info.params = { system: '' };
			} else {
				// Ensure system exists if params exists
				info.params.system = info.params.system ?? '';
			}


			// Ensure info.meta exists after cloning
			if (!info.meta) {
				info.meta = { profile_image_url: '/static/favicon.png', description: '', suggestion_prompts: null, tags: [] };
			} else {
				// Ensure necessary meta fields exist
				info.meta.profile_image_url = info.meta.profile_image_url ?? '/static/favicon.png';
				info.meta.tags = info.meta.tags ?? [];
				info.meta.description = info.meta.description ?? ''; // Initialize if null/undefined
				info.meta.suggestion_prompts = info.meta.suggestion_prompts ?? null; // Initialize if null/undefined
			}

			// Merge existing params from the cloned model into the local params state for the UI components
			// Ensure the local `params` object (used by AdvancedParams) is correctly initialized
			params = { system: '', stop: '', ...info.params }; // Start with defaults, overwrite with info.params
			params.stop = info.params?.stop // Use optional chaining
				? (typeof info.params.stop === 'string' ? info.params.stop.split(',') : (info.params.stop ?? [])).join(
						','
					)
				: ''; // Use empty string for null/undefined to bind correctly to input


			toolIds = info?.meta?.toolIds ?? [];
			filterIds = info?.meta?.filterIds ?? [];
			actionIds = info?.meta?.actionIds ?? [];
			knowledge = (info?.meta?.knowledge ?? []).map((item) => {
				if (item?.collection_name) {
					return {
						id: item.collection_name,
						name: item.name,
						legacy: true
					};
				} else if (item?.collection_names) {
					return {
						name: item.name,
						type: 'collection',
						collection_names: item.collection_names,
						legacy: true
					};
				} else {
					return item;
				}
			});
			capabilities = { ...capabilities, ...(info?.meta?.capabilities ?? {}) };

			// Ensure access_control is initialized properly
			if ('access_control' in info && info.access_control !== null && info.access_control !== undefined) {
				accessControl = info.access_control;
			} else {
				accessControl = {};
			}


			console.log('Loaded model:', info);
			// The reactive block `$: {...}` handles customRoles initialization

		} else {
			// Initialize for a new model if needed
			info = {
				id: '',
				base_model_id: null,
				name: '',
				meta: {
					profile_image_url: '/static/favicon.png',
					description: '',
					suggestion_prompts: null,
					tags: []
				},
				params: {
					system: '',
					custom_roles: [] // Ensure it's initialized for new models too
				}
			};
			params = { system: '', stop: '' }; // Reset local params, include stop
			customRoles = info.params.custom_roles; // Sync customRoles
			accessControl = {}; // Reset access control
		}


		loaded = true;
	});
</script>

{#if loaded}
	{#if onBack}
		<button
			class="flex space-x-1 mb-3 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200" on:click={() => {
				if (onBack) onBack();
			}}
		>
			<div class=" self-center">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="h-4 w-4"
				>
					<path
						fill-rule="evenodd"
						d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
						clip-rule="evenodd"
					/>
				</svg>
			</div>
			<div class=" self-center">{$i18n.t('Back')}</div>
		</button>
	{/if}

	<div class="w-full max-h-full flex justify-center">
		<input
			bind:this={filesInputElement}
			bind:files={inputFiles}
			type="file"
			hidden
			accept="image/*"
			on:change={() => {
				let reader = new FileReader();
				reader.onload = (event) => {
					if (!event.target?.result) return;
					let originalImageUrl = `${event.target.result}`;

					const img = new Image();
					img.src = originalImageUrl;

					img.onload = function () {
						const canvas = document.createElement('canvas');
						const ctx = canvas.getContext('2d');
						if (!ctx) return; // Add null check for context

						// Calculate the aspect ratio of the image
						const aspectRatio = img.width / img.height;

						// Calculate the new width and height to fit within target size (e.g., 250x250)
						let newWidth, newHeight;
						const targetSize = 250; // Define target size
						if (img.width > img.height) {
                            newWidth = targetSize;
                            newHeight = targetSize / aspectRatio;
                        } else {
                            newHeight = targetSize;
                            newWidth = targetSize * aspectRatio;
                        }


						// Set the canvas size (square in this case)
						canvas.width = targetSize;
						canvas.height = targetSize;

						// Fill background if needed (e.g., for transparency handling)
                        // ctx.fillStyle = "#FFFFFF"; // Optional: set background color
                        // ctx.fillRect(0, 0, targetSize, targetSize);

						// Calculate the position to center the image
						const offsetX = (targetSize - newWidth) / 2;
						const offsetY = (targetSize - newHeight) / 2;

						// Draw the image on the canvas
						ctx.drawImage(img, offsetX, offsetY, newWidth, newHeight);

						// Get the base64 representation of the compressed image
						const compressedSrc = canvas.toDataURL('image/png'); // Specify format if needed

						// Display the compressed image
						if (info.meta) info.meta.profile_image_url = compressedSrc;

						inputFiles = null;
						if (filesInputElement) filesInputElement.value = ''; // Clear file input
					};

					img.onerror = function () {
						toast.error("Failed to load image for processing.");
						inputFiles = null;
						if (filesInputElement) filesInputElement.value = ''; // Clear file input
					};
				};

				reader.onerror = function () {
					toast.error("Failed to read the selected file.");
					inputFiles = null;
					if (filesInputElement) filesInputElement.value = ''; // Clear file input
				};


				if (
					inputFiles &&
					inputFiles.length > 0 &&
					['image/gif', 'image/webp', 'image/jpeg', 'image/png', 'image/svg+xml'].includes(
						inputFiles[0]['type']
					)
				) {
					reader.readAsDataURL(inputFiles[0]);
				} else if (inputFiles && inputFiles.length > 0) {
					toast.error(`Unsupported File Type '${inputFiles[0]['type']}'. Please select an image.`);
					inputFiles = null;
                    if (filesInputElement) filesInputElement.value = ''; // Clear file input
				}
			}}
		/>

		{#if !edit || (edit && model)}
			<form
				class="flex flex-col md:flex-row w-full gap-3 md:gap-6"
				on:submit|preventDefault={() => {
					submitHandler();
				}}
			>
				<div class="self-center md:self-start flex-col items-center md:items-start my-2 shrink-0"> <div class="self-center">
						<button
							class="rounded-xl flex shrink-0 items-center {info?.meta?.profile_image_url && info.meta.profile_image_url !==
							'/static/favicon.png'
								? 'bg-transparent'
								: 'bg-white dark:bg-gray-900'} shadow-xl group relative border dark:border-gray-700"
							type="button"
							on:click={() => {
								if(filesInputElement) filesInputElement.click();
							}}
						>
							{#if info?.meta?.profile_image_url}
								<img
									src={info.meta.profile_image_url}
									alt="model profile"
									class="rounded-xl size-72 md:size-60 object-cover shrink-0" />
							{:else}
								<img
									src="/static/favicon.png"
									alt="model profile"
									class=" rounded-xl size-72 md:size-60 object-cover shrink-0" />
							{/if}

							<div class="absolute bottom-0 right-0 z-10">
								<div class="m-1.5">
									<div
										class="shadow-xl p-1 rounded-full border-2 border-white bg-gray-800 text-white group-hover:bg-gray-600 transition dark:border-black dark:bg-white dark:group-hover:bg-gray-200 dark:text-black"
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 16 16"
											fill="currentColor"
											class="size-5"
										>
											<path
												fill-rule="evenodd"
												d="M2 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4Zm10.5 5.707a.5.5 0 0 0-.146-.353l-1-1a.5.5 0 0 0-.708 0L9.354 9.646a.5.5 0 0 1-.708 0L6.354 7.354a.5.5 0 0 0-.708 0l-2 2a.5.5 0 0 0-.146.353V12a.5.5 0 0 0 .5.5h8a.5.5 0 0 0 .5-.5V9.707ZM12 5a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"
												clip-rule="evenodd"
											/>
										</svg>
									</div>
								</div>
							</div>

							<div
								class="absolute top-0 bottom-0 left-0 right-0 bg-white dark:bg-black rounded-lg opacity-0 group-hover:opacity-20 transition"
							></div>
						</button>

						{#if info?.meta?.profile_image_url && info.meta.profile_image_url !== '/static/favicon.png'} <div class="flex w-full mt-1 justify-end">
								<button
									class="px-2 py-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg text-xs"
									on:click={() => {
										if (info.meta) info.meta.profile_image_url = '/static/favicon.png';
									}}
									type="button"
								>
									{$i18n.t('Reset Image')}</button
								>
							</div>
						{/if}
					</div>
				</div>


				<div class="w-full">
					<div class="mt-2 my-2 flex flex-col">
						<div class="flex-1 mb-2"> <label for="model-name" class="text-sm font-semibold mb-1 block">{$i18n.t('Model Name')}</label>
							<input
								id="model-name"
								class="text-xl font-semibold w-full bg-transparent outline-none py-2 px-3 border border-gray-200 dark:border-gray-700 rounded-lg dark:bg-gray-900"
								placeholder={$i18n.t('Enter Model Name')}
								bind:value={name}
								required
							/>
						</div>

						<div class="flex-1">
							<label for="model-id" class="text-sm font-semibold mb-1 block">{$i18n.t('Model ID')}</label>
							<input
								id="model-id"
								class="text-xs w-full bg-transparent text-gray-500 outline-none py-2 px-3 border border-gray-200 dark:border-gray-700 rounded-lg dark:bg-gray-900"
								placeholder={$i18n.t('model-id-will-be-generated')}
								bind:value={id}
								disabled={edit}
								required
							/>
						</div>
					</div>

					{#if preset}
						<div class="my-3"> <label for="base-model-select" class=" text-sm font-semibold mb-1 block">{$i18n.t('Base Model (From)')}</label>
							<div>
								<select
									class="text-sm w-full bg-transparent outline-hidden"
									placeholder="Select a base model (e.g. llama3, gpt-4o)"
									bind:value={info.base_model_id}
									on:change={(e) => {
										addUsage(e.target.value);
									}}
									required
								>
									<option value={null} class=" text-gray-900 dark:text-gray-100 dark:bg-gray-800" disabled selected={info.base_model_id === null}
										>{$i18n.t('-- Select a base model --')}</option
									>
									{#each $models.filter((m) => (model ? m.id !== model.id : true) && !m?.preset && m?.owned_by !== 'arena') as modelOption (modelOption.id)}
										<option value={modelOption.id} class=" text-gray-900 dark:text-gray-100 dark:bg-gray-800">{modelOption.name} ({modelOption.id})</option> {/each}
								</select>
							</div>
						</div>
					{/if}

					<div class="my-3"> <div class="mb-1 flex w-full justify-between items-center">
							<div class=" self-center text-sm font-semibold">{$i18n.t('Description')}</div>

							<button
								class="p-1 px-2 text-xs flex rounded-sm transition text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200" type="button"
								on:click={() => {
									enableDescription = !enableDescription;
								}}
							>
								{#if !enableDescription}
									<span class="ml-2 self-center">{$i18n.t('Default')}</span>
								{:else}
									<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
								{/if}
							</button>
						</div>

						{#if enableDescription}
							<Textarea
								className=" text-sm w-full bg-transparent outline-none resize-none overflow-y-hidden "
								placeholder={$i18n.t('Add a short description about what this model does')}
								bind:value={info.meta.description}
							/>
						{/if}
					</div>

					<div class=" mt-2 my-3"> <div class=" text-sm font-semibold mb-1">{$i18n.t('Tags')}</div> <div class="">
							<Tags
								tags={info?.meta?.tags ?? []}
								on:delete={(e) => {
									const tagName = e.detail;
									if (info.meta?.tags) {
										info.meta.tags = info.meta.tags.filter((tag) => tag.name !== tagName);
									}
								}}
								on:add={(e) => {
									const tagName = e.detail;
									if (!info.meta) info.meta = {}; // Ensure meta exists
									if (!(info.meta.tags ?? null)) {
										info.meta.tags = [{ name: tagName }];
									} else {
										// Avoid adding duplicate tags
										if (!info.meta.tags.some(tag => tag.name === tagName)) {
											info.meta.tags = [...info.meta.tags, { name: tagName }];
										} else {
											toast.info(`Tag "${tagName}" already exists.`);
										}
									}
								}}
							/>
						</div>
					</div>

					<div class="my-3"> <div class=" text-sm font-semibold mb-1">{$i18n.t('Access Control')}</div> <div class="px-3 py-2 bg-gray-50 dark:bg-gray-950 rounded-lg border dark:border-gray-800"> <AccessControl
								bind:accessControl
								accessRoles={['read', 'write']}
								allowPublic={$user?.permissions?.sharing?.public_models || $user?.role === 'admin'}
							/>
						</div>
					</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-3" /> <div class="my-3"> <div class="flex w-full justify-between mb-2"> <div class=" self-center text-sm font-semibold">{$i18n.t('Model Params')}</div>
						</div>

						<div class="mt-2">
							<div class="my-1">
								<div class=" text-xs font-semibold mb-2">{$i18n.t('System Prompt')}</div>
								<div>
									<Textarea
										className=" text-sm w-full bg-transparent outline-none resize-none overflow-y-hidden "
										placeholder={`Write your model system prompt content here\ne.g.) You are Mario from Super Mario Bros, acting as an assistant.`}
										rows={4}
										bind:value={info.params.system}
									/>
								</div>
							</div>

							<div class="my-1 border-t border-gray-100 dark:border-gray-850 pt-1.5">
							  <div class=" text-xs font-semibold mb-2">{$i18n.t('Custom Roles')}</div>
							  {#if customRoles.length > 0}
								<div class="flex flex-col gap-2.5 mb-2.5">
								  {#each customRoles as roleItem, i (i)}
									<div class="flex items-start gap-2">
									  <div class="flex-1 flex flex-row gap-2 items-start">
										<input
										  bind:value={roleItem.role}
										  placeholder={$i18n.t("Role Name")}
										  class="w-1/3 text-sm bg-transparent outline-none py-2 px-3 border border-gray-200 dark:border-gray-700 rounded-lg dark:bg-gray-900"
										  aria-label="Role Name"
										/>
										<Textarea
										  bind:value={roleItem.value}
										  placeholder={$i18n.t("Role Value")}
										  className=" text-sm w-full bg-transparent outline-none py-2 px-3 border border-gray-200 dark:border-gray-700 rounded-lg dark:bg-gray-900 resize-none overflow-y-hidden "
										  rows={4}										  
										/>
									  </div>
									  <button
										class="btn p-2 variant-soft-error !text-error-500 mt-1" on:click={() => deleteCustomRole(i)}
										title={$i18n.t('Delete Role')}
										type="button"
									  >
										<GarbageBin /> </button>
									</div>
								  {/each}
								</div>
							  {/if}

							  <div class="mt-1">
								<button
								  class="btn variant-soft text-xs inline-flex items-center" on:click={addCustomRole}
								  title={$i18n.t('Add Custom Role')}
								  type="button"
								>
								  <span class="mr-1"><Plus /></span>
								  {$i18n.t('Add Role')}
								</button>
							  </div>
							  <p class="text-xs text-gray-500 mt-1">
								{$i18n.t(
								 'Define custom roles and their corresponding values to be included in the request sent to the LLM.'
								)}
							  </p>
							</div>
							<div class="flex w-full justify-between border-t border-gray-100 dark:border-gray-850 pt-1.5 mt-1.5">
								<div class=" self-center text-xs font-semibold">
									{$i18n.t('Advanced Params')}
								</div>

								<button
									class="p-1 px-3 text-xs flex rounded-sm transition text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200" type="button"
									on:click={() => {
										showAdvanced = !showAdvanced;
									}}
								>
									{#if showAdvanced}
										<span class="ml-2 self-center">{$i18n.t('Hide')}</span>
									{:else}
										<span class="ml-2 self-center">{$i18n.t('Show')}</span>
									{/if}
								</button>
							</div>

							{#if showAdvanced}
								<div class="my-2">
									<AdvancedParams
										admin={true}
										bind:params
										on:change={(e) => {
											// Merge changed advanced params back into info.params
											if (!info.params) info.params = {}; // Ensure params exists
											info.params = { ...info.params, ...params };
										}}
									/>
								</div>
							{/if}
						</div>
					</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-3" /> <div class="my-3"> <div class="flex w-full justify-between items-center">
							<div class="flex w-full justify-between items-center">
								<div class=" self-center text-sm font-semibold">
									{$i18n.t('Prompt suggestions')}
								</div>

								<button
									class="p-1 px-2 text-xs flex rounded-sm transition text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200" type="button"
									on:click={() => {
										if (!info.meta) info.meta = {}; // Ensure meta exists
										if ((info.meta.suggestion_prompts ?? null) === null) {
											info.meta.suggestion_prompts = [{ content: '' }];
										} else {
											info.meta.suggestion_prompts = null;
										}
                                        info.meta = info.meta; // Trigger reactivity
									}}
								>
									{#if (info?.meta?.suggestion_prompts ?? null) === null}
										<span class="ml-2 self-center">{$i18n.t('Default')}</span>
									{:else}
										<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
									{/if}
								</button>
							</div>

							{#if (info?.meta?.suggestion_prompts ?? null) !== null}
								<button
									class="p-1 px-2 text-xs flex rounded-sm transition text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200" type="button"
									on:click={() => {
										if (!info.meta) info.meta = {}; // Ensure meta exists
										if (
											!info.meta.suggestion_prompts || // Ensure array exists
											info.meta.suggestion_prompts.length === 0 ||
											info.meta.suggestion_prompts.at(-1)?.content !== '' // Use optional chaining
										) {
                                            if (!info.meta.suggestion_prompts) info.meta.suggestion_prompts = []; // Initialize if null/undefined
											info.meta.suggestion_prompts = [
												...info.meta.suggestion_prompts,
												{ content: '' }
											];
										}
									}}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="w-4 h-4"
									>
										<path
											d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z"
										/>
									</svg>
								</button>
							{/if}
						</div>

						{#if info?.meta?.suggestion_prompts}
							<div class="flex flex-col space-y-1 mt-1 mb-3">
								{#if info.meta.suggestion_prompts.length > 0}
									{#each info.meta.suggestion_prompts as prompt, promptIdx (promptIdx)}
										<div class=" flex rounded-lg border border-gray-200 dark:border-gray-700">
											<input
												class=" text-sm w-full bg-transparent outline-none px-2 py-1 border-r border-gray-200 dark:border-gray-700"
												placeholder={$i18n.t('Write a prompt suggestion (e.g. Who are you?)')}
												bind:value={prompt.content}
											/>

											<button
												class="px-2 hover:bg-red-100 dark:hover:bg-red-900/50"
												type="button"
												on:click={() => {
													if (info.meta?.suggestion_prompts) {
														info.meta.suggestion_prompts.splice(promptIdx, 1);
														info.meta.suggestion_prompts = info.meta.suggestion_prompts; // Trigger reactivity
													}
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 20 20"
													fill="currentColor"
													class="w-4 h-4 text-red-500"
												>
													<path
														d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
													/>
												</svg>
											</button>
										</div>
									{/each}
								{:else}
									<div class="text-xs text-center text-gray-500">{$i18n.t('No suggestion prompts')}</div>
								{/if}
							</div>
						{/if}
					</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-3" /> <div class="my-3"> <div class=" text-sm font-semibold mb-1">{$i18n.t('Knowledge Base')}</div> <Knowledge bind:selectedKnowledge={knowledge} collections={$knowledgeCollections} />
					</div>

					<div class="my-3"> <div class=" text-sm font-semibold mb-1">{$i18n.t('Tools')}</div> <ToolsSelector bind:selectedToolIds={toolIds} tools={$tools} />
					</div>

					<div class="my-3"> <div class=" text-sm font-semibold mb-1">{$i18n.t('Filters')}</div> <FiltersSelector
							bind:selectedFilterIds={filterIds}
							filters={$functions.filter((func) => func.type === 'filter')}
						/>
					</div>

					<div class="my-3"> <div class=" text-sm font-semibold mb-1">{$i18n.t('Actions')}</div> <ActionsSelector
							bind:selectedActionIds={actionIds}
							actions={$functions.filter((func) => func.type === 'action')}
						/>
					</div>

					<div class="my-3"> <div class=" text-sm font-semibold mb-1">{$i18n.t('Capabilities')}</div> <Capabilities bind:capabilities />
					</div>

					<div class="my-3 text-gray-500 dark:text-gray-400"> <div class="flex w-full justify-between mb-2">
							<div class=" self-center text-sm font-semibold text-gray-700 dark:text-gray-300">{$i18n.t('JSON Preview')}</div> <button
								class="p-1 px-3 text-xs flex rounded-sm transition text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200" type="button"
								on:click={() => {
									showPreview = !showPreview;
								}}
							>
								{#if showPreview}
									<span class="ml-2 self-center">{$i18n.t('Hide')}</span>
								{:else}
									<span class="ml-2 self-center">{$i18n.t('Show')}</span>
								{/if}
							</button>
						</div>

						{#if showPreview}
							<div>
								<textarea
									class="text-xs font-mono w-full bg-gray-50 dark:bg-gray-950 outline-none resize-none p-2 rounded border border-gray-200 dark:border-gray-700"
									rows="10"
									value={JSON.stringify(info, null, 2)}
									readonly
								/>
							</div>
						{/if}
					</div>

					<div class="my-3 flex justify-end pb-20"> <button
							class=" text-sm px-3 py-2 transition rounded-lg {loading
								? ' cursor-not-allowed bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
								: 'bg-black hover:bg-gray-900 text-white dark:bg-white dark:hover:bg-gray-100 dark:text-black'} flex w-full justify-center font-medium" type="submit"
							disabled={loading}
						>
							<div class=" self-center">
								{#if edit}
									{$i18n.t('Save & Update')}
								{:else}
									{$i18n.t('Save & Create')}
								{/if}
							</div>

							{#if loading}
								<div class="ml-1.5 self-center">
									<svg
										class=" w-4 h-4 animate-spin" viewBox="0 0 24 24"
										fill="currentColor"
										xmlns="http://www.w3.org/2000/svg"
										><style>
											.spinner_ajPY {
												transform-origin: center;
												animation: spinner_AtaB 0.75s infinite linear;
											}
											@keyframes spinner_AtaB {
												100% {
													transform: rotate(360deg);
												}
											}
										</style><path
											d="M12,1A11,11,0,1,0,23,12,11,11,0,0,0,12,1Zm0,19a8,8,0,1,1,8-8A8,8,0,0,1,12,20Z"
											opacity=".25"
										/><path
											d="M10.14,1.16a11,11,0,0,0-9,8.92A1.59,1.59,0,0,0,2.46,12,1.52,1.52,0,0,0,4.11,10.7a8,8,0,0,1,6.66-6.61A1.42,1.42,0,0,0,12,2.69h0A1.57,1.57,0,0,0,10.14,1.16Z"
											class="spinner_ajPY"
										/></svg
									>
								</div>
							{/if}
						</button>
					</div>
				</div>
			</form>
		{/if}
	</div>
{/if}

