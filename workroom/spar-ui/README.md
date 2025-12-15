# Agent Platform UI components

## Publishing changes

Spar UI uses [Changesets](https://github.com/changesets/changesets) workflow for managing changes and publishing the package. To tag your changes to be included in the changelog:

1. Run `npm run changeset` in the `./workroom/spar-ui` directory and select `@sema4ai/spar-ui` to mark the changes made.
2. Follow the instructions to tag your changes as [major, minor or a patch](https://semver.org/#summary).
    a. It will prompt for which packages need a **major** verison bump first. If none require a major, hit Enter to shift to _minor_, and so forth.
3. Add a human readable and meaningful summary on the changes made describing what has changed and the impact of these changes.

A "Spar UI: Next Release" Pull Request will collect all unreleased changes that are merged to `main`. Merging that PR will create and publish the release and ping about the at #design channel.
