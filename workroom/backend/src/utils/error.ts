import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import { ZodError } from 'zod';

/**
 * Format a Zod error as a string for better readability while logging
 * @see {} This may not be needed for Zod v4
 */
export const formatZodError = (error: ZodError): string => {
  return error.issues
    .map((issue) => {
      const pathStr = issue.path.length > 0 ? ` @ ${issue.path.join('.')}` : '';

      switch (issue.code) {
        case 'invalid_type':
          return `Invalid type: expected '${issue.expected}', received '${issue.received}'${pathStr}`;

        case 'invalid_literal':
          return `Invalid literal: expected ${JSON.stringify(issue.expected)}, received ${JSON.stringify(issue.received)}${pathStr}`;

        case 'custom':
          return `Custom validation failed${pathStr}${issue.params ? `: ${JSON.stringify(issue.params)}` : ''}`;

        case 'invalid_union':
          return `Invalid union: none of the union types matched${pathStr}`;

        case 'invalid_union_discriminator':
          return `Invalid union discriminator: expected one of [${issue.options.join(', ')}]${pathStr}`;

        case 'invalid_enum_value':
          return `Invalid enum value: expected one of [${issue.options.join(', ')}], received ${issue.received}${pathStr}`;

        case 'unrecognized_keys':
          return `Unrecognized keys: [${issue.keys.join(', ')}]${pathStr}`;

        case 'invalid_arguments':
          return `Invalid function arguments${pathStr}`;

        case 'invalid_return_type':
          return `Invalid function return type${pathStr}`;

        case 'invalid_date':
          return `Invalid date${pathStr}`;

        case 'invalid_string': {
          const validation = issue.validation;
          let validationMsg = '';

          if (typeof validation === 'string') {
            validationMsg = validation;
          } else if (typeof validation === 'object') {
            if ('includes' in validation) {
              validationMsg = `includes "${validation.includes}"${validation.position !== undefined ? ` at position ${validation.position}` : ''}`;
            } else if ('startsWith' in validation) {
              validationMsg = `starts with "${validation.startsWith}"`;
            } else if ('endsWith' in validation) {
              validationMsg = `ends with "${validation.endsWith}"`;
            }
          }

          return `Invalid string: must ${validationMsg}${pathStr}`;
        }

        case 'too_small':
          if (issue.exact) {
            return `${issue.type} must be exactly ${issue.minimum}${pathStr}`;
          } else {
            const operator = issue.inclusive ? '>=' : '>';
            return `${issue.type} must be ${operator} ${issue.minimum}${pathStr}`;
          }

        case 'too_big':
          if (issue.exact) {
            return `${issue.type} must be exactly ${issue.maximum}${pathStr}`;
          } else {
            const operator = issue.inclusive ? '<=' : '<';
            return `${issue.type} must be ${operator} ${issue.maximum}${pathStr}`;
          }

        case 'invalid_intersection_types':
          return `Invalid intersection types${pathStr}`;

        case 'not_multiple_of':
          return `Number must be a multiple of ${issue.multipleOf}${pathStr}`;

        case 'not_finite':
          return `Number must be finite${pathStr}`;

        default:
          exhaustiveCheck(issue);
      }
    })
    .join(', ');
};
