# Storybook Configuration

This directory contains the Storybook configuration for the SAI SDK.

## Files

### `main.ts`

Main Storybook configuration:

- Defines story file locations (`../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)`)
- Configures addons (essentials, links, interactions)
- Sets up Vite as the framework
- Enables autodocs

### `preview.ts`

Preview configuration:

- Configures global parameters
- Sets up action matchers
- Defines control matchers for colors and dates

## Framework

Using **@storybook/react-vite** for:

- Fast HMR (Hot Module Replacement)
- Native ES modules support
- TypeScript support out of the box
- Optimized builds

## Addons

- **@storybook/addon-essentials**: Core addons (docs, controls, actions, etc.)
- **@storybook/addon-links**: Link between stories
- **@storybook/addon-interactions**: Test user interactions

## Documentation

Stories automatically generate documentation using:

- Component JSDoc comments
- Story descriptions
- ArgTypes configuration
- MDX files for custom docs

## Customization

To modify the Storybook configuration:

1. **Add addons**: Update `main.ts` addons array
2. **Change theme**: Modify `preview.ts` parameters
3. **Add global decorators**: Use `preview.ts` decorators array
4. **Configure build**: Update Vite options in `main.ts`

## Build Output

Static builds are generated in `../storybook-static/`
