function TN(u, f) {
  for (var v = 0; v < f.length; v++) {
    const y = f[v];
    if (typeof y != "string" && !Array.isArray(y)) {
      for (const S in y)
        if (S !== "default" && !(S in u)) {
          const T = Object.getOwnPropertyDescriptor(y, S);
          T && Object.defineProperty(u, S, T.get ? T : {
            enumerable: !0,
            get: () => y[S]
          });
        }
    }
  }
  return Object.freeze(Object.defineProperty(u, Symbol.toStringTag, { value: "Module" }));
}
function ew(u) {
  return u && u.__esModule && Object.prototype.hasOwnProperty.call(u, "default") ? u.default : u;
}
var tC = { exports: {} }, Ut = {};
/**
 * @license React
 * react.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var uR;
function RN() {
  if (uR) return Ut;
  uR = 1;
  var u = Symbol.for("react.element"), f = Symbol.for("react.portal"), v = Symbol.for("react.fragment"), y = Symbol.for("react.strict_mode"), S = Symbol.for("react.profiler"), T = Symbol.for("react.provider"), _ = Symbol.for("react.context"), g = Symbol.for("react.forward_ref"), L = Symbol.for("react.suspense"), z = Symbol.for("react.memo"), A = Symbol.for("react.lazy"), F = Symbol.iterator;
  function U(k) {
    return k === null || typeof k != "object" ? null : (k = F && k[F] || k["@@iterator"], typeof k == "function" ? k : null);
  }
  var te = { isMounted: function() {
    return !1;
  }, enqueueForceUpdate: function() {
  }, enqueueReplaceState: function() {
  }, enqueueSetState: function() {
  } }, B = Object.assign, M = {};
  function j(k, I, ye) {
    this.props = k, this.context = I, this.refs = M, this.updater = ye || te;
  }
  j.prototype.isReactComponent = {}, j.prototype.setState = function(k, I) {
    if (typeof k != "object" && typeof k != "function" && k != null) throw Error("setState(...): takes an object of state variables to update or a function which returns an object of state variables.");
    this.updater.enqueueSetState(this, k, I, "setState");
  }, j.prototype.forceUpdate = function(k) {
    this.updater.enqueueForceUpdate(this, k, "forceUpdate");
  };
  function ce() {
  }
  ce.prototype = j.prototype;
  function De(k, I, ye) {
    this.props = k, this.context = I, this.refs = M, this.updater = ye || te;
  }
  var de = De.prototype = new ce();
  de.constructor = De, B(de, j.prototype), de.isPureReactComponent = !0;
  var ue = Array.isArray, q = Object.prototype.hasOwnProperty, se = { current: null }, Ce = { key: !0, ref: !0, __self: !0, __source: !0 };
  function Ge(k, I, ye) {
    var Re, be = {}, Le = null, ze = null;
    if (I != null) for (Re in I.ref !== void 0 && (ze = I.ref), I.key !== void 0 && (Le = "" + I.key), I) q.call(I, Re) && !Ce.hasOwnProperty(Re) && (be[Re] = I[Re]);
    var we = arguments.length - 2;
    if (we === 1) be.children = ye;
    else if (1 < we) {
      for (var Ye = Array(we), et = 0; et < we; et++) Ye[et] = arguments[et + 2];
      be.children = Ye;
    }
    if (k && k.defaultProps) for (Re in we = k.defaultProps, we) be[Re] === void 0 && (be[Re] = we[Re]);
    return { $$typeof: u, type: k, key: Le, ref: ze, props: be, _owner: se.current };
  }
  function _t(k, I) {
    return { $$typeof: u, type: k.type, key: I, ref: k.ref, props: k.props, _owner: k._owner };
  }
  function x(k) {
    return typeof k == "object" && k !== null && k.$$typeof === u;
  }
  function ge(k) {
    var I = { "=": "=0", ":": "=2" };
    return "$" + k.replace(/[=:]/g, function(ye) {
      return I[ye];
    });
  }
  var je = /\/+/g;
  function Qe(k, I) {
    return typeof k == "object" && k !== null && k.key != null ? ge("" + k.key) : I.toString(36);
  }
  function Pe(k, I, ye, Re, be) {
    var Le = typeof k;
    (Le === "undefined" || Le === "boolean") && (k = null);
    var ze = !1;
    if (k === null) ze = !0;
    else switch (Le) {
      case "string":
      case "number":
        ze = !0;
        break;
      case "object":
        switch (k.$$typeof) {
          case u:
          case f:
            ze = !0;
        }
    }
    if (ze) return ze = k, be = be(ze), k = Re === "" ? "." + Qe(ze, 0) : Re, ue(be) ? (ye = "", k != null && (ye = k.replace(je, "$&/") + "/"), Pe(be, I, ye, "", function(et) {
      return et;
    })) : be != null && (x(be) && (be = _t(be, ye + (!be.key || ze && ze.key === be.key ? "" : ("" + be.key).replace(je, "$&/") + "/") + k)), I.push(be)), 1;
    if (ze = 0, Re = Re === "" ? "." : Re + ":", ue(k)) for (var we = 0; we < k.length; we++) {
      Le = k[we];
      var Ye = Re + Qe(Le, we);
      ze += Pe(Le, I, ye, Ye, be);
    }
    else if (Ye = U(k), typeof Ye == "function") for (k = Ye.call(k), we = 0; !(Le = k.next()).done; ) Le = Le.value, Ye = Re + Qe(Le, we++), ze += Pe(Le, I, ye, Ye, be);
    else if (Le === "object") throw I = String(k), Error("Objects are not valid as a React child (found: " + (I === "[object Object]" ? "object with keys {" + Object.keys(k).join(", ") + "}" : I) + "). If you meant to render a collection of children, use an array instead.");
    return ze;
  }
  function pt(k, I, ye) {
    if (k == null) return k;
    var Re = [], be = 0;
    return Pe(k, Re, "", "", function(Le) {
      return I.call(ye, Le, be++);
    }), Re;
  }
  function vt(k) {
    if (k._status === -1) {
      var I = k._result;
      I = I(), I.then(function(ye) {
        (k._status === 0 || k._status === -1) && (k._status = 1, k._result = ye);
      }, function(ye) {
        (k._status === 0 || k._status === -1) && (k._status = 2, k._result = ye);
      }), k._status === -1 && (k._status = 0, k._result = I);
    }
    if (k._status === 1) return k._result.default;
    throw k._result;
  }
  var ot = { current: null }, ie = { transition: null }, Ie = { ReactCurrentDispatcher: ot, ReactCurrentBatchConfig: ie, ReactCurrentOwner: se };
  function ke() {
    throw Error("act(...) is not supported in production builds of React.");
  }
  return Ut.Children = { map: pt, forEach: function(k, I, ye) {
    pt(k, function() {
      I.apply(this, arguments);
    }, ye);
  }, count: function(k) {
    var I = 0;
    return pt(k, function() {
      I++;
    }), I;
  }, toArray: function(k) {
    return pt(k, function(I) {
      return I;
    }) || [];
  }, only: function(k) {
    if (!x(k)) throw Error("React.Children.only expected to receive a single React element child.");
    return k;
  } }, Ut.Component = j, Ut.Fragment = v, Ut.Profiler = S, Ut.PureComponent = De, Ut.StrictMode = y, Ut.Suspense = L, Ut.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = Ie, Ut.act = ke, Ut.cloneElement = function(k, I, ye) {
    if (k == null) throw Error("React.cloneElement(...): The argument must be a React element, but you passed " + k + ".");
    var Re = B({}, k.props), be = k.key, Le = k.ref, ze = k._owner;
    if (I != null) {
      if (I.ref !== void 0 && (Le = I.ref, ze = se.current), I.key !== void 0 && (be = "" + I.key), k.type && k.type.defaultProps) var we = k.type.defaultProps;
      for (Ye in I) q.call(I, Ye) && !Ce.hasOwnProperty(Ye) && (Re[Ye] = I[Ye] === void 0 && we !== void 0 ? we[Ye] : I[Ye]);
    }
    var Ye = arguments.length - 2;
    if (Ye === 1) Re.children = ye;
    else if (1 < Ye) {
      we = Array(Ye);
      for (var et = 0; et < Ye; et++) we[et] = arguments[et + 2];
      Re.children = we;
    }
    return { $$typeof: u, type: k.type, key: be, ref: Le, props: Re, _owner: ze };
  }, Ut.createContext = function(k) {
    return k = { $$typeof: _, _currentValue: k, _currentValue2: k, _threadCount: 0, Provider: null, Consumer: null, _defaultValue: null, _globalName: null }, k.Provider = { $$typeof: T, _context: k }, k.Consumer = k;
  }, Ut.createElement = Ge, Ut.createFactory = function(k) {
    var I = Ge.bind(null, k);
    return I.type = k, I;
  }, Ut.createRef = function() {
    return { current: null };
  }, Ut.forwardRef = function(k) {
    return { $$typeof: g, render: k };
  }, Ut.isValidElement = x, Ut.lazy = function(k) {
    return { $$typeof: A, _payload: { _status: -1, _result: k }, _init: vt };
  }, Ut.memo = function(k, I) {
    return { $$typeof: z, type: k, compare: I === void 0 ? null : I };
  }, Ut.startTransition = function(k) {
    var I = ie.transition;
    ie.transition = {};
    try {
      k();
    } finally {
      ie.transition = I;
    }
  }, Ut.unstable_act = ke, Ut.useCallback = function(k, I) {
    return ot.current.useCallback(k, I);
  }, Ut.useContext = function(k) {
    return ot.current.useContext(k);
  }, Ut.useDebugValue = function() {
  }, Ut.useDeferredValue = function(k) {
    return ot.current.useDeferredValue(k);
  }, Ut.useEffect = function(k, I) {
    return ot.current.useEffect(k, I);
  }, Ut.useId = function() {
    return ot.current.useId();
  }, Ut.useImperativeHandle = function(k, I, ye) {
    return ot.current.useImperativeHandle(k, I, ye);
  }, Ut.useInsertionEffect = function(k, I) {
    return ot.current.useInsertionEffect(k, I);
  }, Ut.useLayoutEffect = function(k, I) {
    return ot.current.useLayoutEffect(k, I);
  }, Ut.useMemo = function(k, I) {
    return ot.current.useMemo(k, I);
  }, Ut.useReducer = function(k, I, ye) {
    return ot.current.useReducer(k, I, ye);
  }, Ut.useRef = function(k) {
    return ot.current.useRef(k);
  }, Ut.useState = function(k) {
    return ot.current.useState(k);
  }, Ut.useSyncExternalStore = function(k, I, ye) {
    return ot.current.useSyncExternalStore(k, I, ye);
  }, Ut.useTransition = function() {
    return ot.current.useTransition();
  }, Ut.version = "18.3.1", Ut;
}
var Gv = { exports: {} };
Gv.exports;
var sR;
function wN() {
  return sR || (sR = 1, function(u, f) {
    var v = {};
    /**
     * @license React
     * react.development.js
     *
     * Copyright (c) Facebook, Inc. and its affiliates.
     *
     * This source code is licensed under the MIT license found in the
     * LICENSE file in the root directory of this source tree.
     */
    v.NODE_ENV !== "production" && function() {
      typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u" && typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart == "function" && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart(new Error());
      var y = "18.3.1", S = Symbol.for("react.element"), T = Symbol.for("react.portal"), _ = Symbol.for("react.fragment"), g = Symbol.for("react.strict_mode"), L = Symbol.for("react.profiler"), z = Symbol.for("react.provider"), A = Symbol.for("react.context"), F = Symbol.for("react.forward_ref"), U = Symbol.for("react.suspense"), te = Symbol.for("react.suspense_list"), B = Symbol.for("react.memo"), M = Symbol.for("react.lazy"), j = Symbol.for("react.offscreen"), ce = Symbol.iterator, De = "@@iterator";
      function de(C) {
        if (C === null || typeof C != "object")
          return null;
        var D = ce && C[ce] || C[De];
        return typeof D == "function" ? D : null;
      }
      var ue = {
        /**
         * @internal
         * @type {ReactComponent}
         */
        current: null
      }, q = {
        transition: null
      }, se = {
        current: null,
        // Used to reproduce behavior of `batchedUpdates` in legacy mode.
        isBatchingLegacy: !1,
        didScheduleLegacyUpdate: !1
      }, Ce = {
        /**
         * @internal
         * @type {ReactComponent}
         */
        current: null
      }, Ge = {}, _t = null;
      function x(C) {
        _t = C;
      }
      Ge.setExtraStackFrame = function(C) {
        _t = C;
      }, Ge.getCurrentStack = null, Ge.getStackAddendum = function() {
        var C = "";
        _t && (C += _t);
        var D = Ge.getCurrentStack;
        return D && (C += D() || ""), C;
      };
      var ge = !1, je = !1, Qe = !1, Pe = !1, pt = !1, vt = {
        ReactCurrentDispatcher: ue,
        ReactCurrentBatchConfig: q,
        ReactCurrentOwner: Ce
      };
      vt.ReactDebugCurrentFrame = Ge, vt.ReactCurrentActQueue = se;
      function ot(C) {
        {
          for (var D = arguments.length, K = new Array(D > 1 ? D - 1 : 0), ee = 1; ee < D; ee++)
            K[ee - 1] = arguments[ee];
          Ie("warn", C, K);
        }
      }
      function ie(C) {
        {
          for (var D = arguments.length, K = new Array(D > 1 ? D - 1 : 0), ee = 1; ee < D; ee++)
            K[ee - 1] = arguments[ee];
          Ie("error", C, K);
        }
      }
      function Ie(C, D, K) {
        {
          var ee = vt.ReactDebugCurrentFrame, Ee = ee.getStackAddendum();
          Ee !== "" && (D += "%s", K = K.concat([Ee]));
          var Ke = K.map(function(He) {
            return String(He);
          });
          Ke.unshift("Warning: " + D), Function.prototype.apply.call(console[C], console, Ke);
        }
      }
      var ke = {};
      function k(C, D) {
        {
          var K = C.constructor, ee = K && (K.displayName || K.name) || "ReactClass", Ee = ee + "." + D;
          if (ke[Ee])
            return;
          ie("Can't call %s on a component that is not yet mounted. This is a no-op, but it might indicate a bug in your application. Instead, assign to `this.state` directly or define a `state = {};` class property with the desired state in the %s component.", D, ee), ke[Ee] = !0;
        }
      }
      var I = {
        /**
         * Checks whether or not this composite component is mounted.
         * @param {ReactClass} publicInstance The instance we want to test.
         * @return {boolean} True if mounted, false otherwise.
         * @protected
         * @final
         */
        isMounted: function(C) {
          return !1;
        },
        /**
         * Forces an update. This should only be invoked when it is known with
         * certainty that we are **not** in a DOM transaction.
         *
         * You may want to call this when you know that some deeper aspect of the
         * component's state has changed but `setState` was not called.
         *
         * This will not invoke `shouldComponentUpdate`, but it will invoke
         * `componentWillUpdate` and `componentDidUpdate`.
         *
         * @param {ReactClass} publicInstance The instance that should rerender.
         * @param {?function} callback Called after component is updated.
         * @param {?string} callerName name of the calling function in the public API.
         * @internal
         */
        enqueueForceUpdate: function(C, D, K) {
          k(C, "forceUpdate");
        },
        /**
         * Replaces all of the state. Always use this or `setState` to mutate state.
         * You should treat `this.state` as immutable.
         *
         * There is no guarantee that `this.state` will be immediately updated, so
         * accessing `this.state` after calling this method may return the old value.
         *
         * @param {ReactClass} publicInstance The instance that should rerender.
         * @param {object} completeState Next state.
         * @param {?function} callback Called after component is updated.
         * @param {?string} callerName name of the calling function in the public API.
         * @internal
         */
        enqueueReplaceState: function(C, D, K, ee) {
          k(C, "replaceState");
        },
        /**
         * Sets a subset of the state. This only exists because _pendingState is
         * internal. This provides a merging strategy that is not available to deep
         * properties which is confusing. TODO: Expose pendingState or don't use it
         * during the merge.
         *
         * @param {ReactClass} publicInstance The instance that should rerender.
         * @param {object} partialState Next partial state to be merged with state.
         * @param {?function} callback Called after component is updated.
         * @param {?string} Name of the calling function in the public API.
         * @internal
         */
        enqueueSetState: function(C, D, K, ee) {
          k(C, "setState");
        }
      }, ye = Object.assign, Re = {};
      Object.freeze(Re);
      function be(C, D, K) {
        this.props = C, this.context = D, this.refs = Re, this.updater = K || I;
      }
      be.prototype.isReactComponent = {}, be.prototype.setState = function(C, D) {
        if (typeof C != "object" && typeof C != "function" && C != null)
          throw new Error("setState(...): takes an object of state variables to update or a function which returns an object of state variables.");
        this.updater.enqueueSetState(this, C, D, "setState");
      }, be.prototype.forceUpdate = function(C) {
        this.updater.enqueueForceUpdate(this, C, "forceUpdate");
      };
      {
        var Le = {
          isMounted: ["isMounted", "Instead, make sure to clean up subscriptions and pending requests in componentWillUnmount to prevent memory leaks."],
          replaceState: ["replaceState", "Refactor your code to use setState instead (see https://github.com/facebook/react/issues/3236)."]
        }, ze = function(C, D) {
          Object.defineProperty(be.prototype, C, {
            get: function() {
              ot("%s(...) is deprecated in plain JavaScript React classes. %s", D[0], D[1]);
            }
          });
        };
        for (var we in Le)
          Le.hasOwnProperty(we) && ze(we, Le[we]);
      }
      function Ye() {
      }
      Ye.prototype = be.prototype;
      function et(C, D, K) {
        this.props = C, this.context = D, this.refs = Re, this.updater = K || I;
      }
      var ut = et.prototype = new Ye();
      ut.constructor = et, ye(ut, be.prototype), ut.isPureReactComponent = !0;
      function Ht() {
        var C = {
          current: null
        };
        return Object.seal(C), C;
      }
      var Te = Array.isArray;
      function Wt(C) {
        return Te(C);
      }
      function Fn(C) {
        {
          var D = typeof Symbol == "function" && Symbol.toStringTag, K = D && C[Symbol.toStringTag] || C.constructor.name || "Object";
          return K;
        }
      }
      function Ln(C) {
        try {
          return Gn(C), !1;
        } catch {
          return !0;
        }
      }
      function Gn(C) {
        return "" + C;
      }
      function _a(C) {
        if (Ln(C))
          return ie("The provided key is an unsupported type %s. This value must be coerced to a string before before using it here.", Fn(C)), Gn(C);
      }
      function di(C, D, K) {
        var ee = C.displayName;
        if (ee)
          return ee;
        var Ee = D.displayName || D.name || "";
        return Ee !== "" ? K + "(" + Ee + ")" : K;
      }
      function Ir(C) {
        return C.displayName || "Context";
      }
      function ir(C) {
        if (C == null)
          return null;
        if (typeof C.tag == "number" && ie("Received an unexpected object in getComponentNameFromType(). This is likely a bug in React. Please file an issue."), typeof C == "function")
          return C.displayName || C.name || null;
        if (typeof C == "string")
          return C;
        switch (C) {
          case _:
            return "Fragment";
          case T:
            return "Portal";
          case L:
            return "Profiler";
          case g:
            return "StrictMode";
          case U:
            return "Suspense";
          case te:
            return "SuspenseList";
        }
        if (typeof C == "object")
          switch (C.$$typeof) {
            case A:
              var D = C;
              return Ir(D) + ".Consumer";
            case z:
              var K = C;
              return Ir(K._context) + ".Provider";
            case F:
              return di(C, C.render, "ForwardRef");
            case B:
              var ee = C.displayName || null;
              return ee !== null ? ee : ir(C.type) || "Memo";
            case M: {
              var Ee = C, Ke = Ee._payload, He = Ee._init;
              try {
                return ir(He(Ke));
              } catch {
                return null;
              }
            }
          }
        return null;
      }
      var dr = Object.prototype.hasOwnProperty, pr = {
        key: !0,
        ref: !0,
        __self: !0,
        __source: !0
      }, Pr, pi, Qn;
      Qn = {};
      function br(C) {
        if (dr.call(C, "ref")) {
          var D = Object.getOwnPropertyDescriptor(C, "ref").get;
          if (D && D.isReactWarning)
            return !1;
        }
        return C.ref !== void 0;
      }
      function la(C) {
        if (dr.call(C, "key")) {
          var D = Object.getOwnPropertyDescriptor(C, "key").get;
          if (D && D.isReactWarning)
            return !1;
        }
        return C.key !== void 0;
      }
      function eo(C, D) {
        var K = function() {
          Pr || (Pr = !0, ie("%s: `key` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://reactjs.org/link/special-props)", D));
        };
        K.isReactWarning = !0, Object.defineProperty(C, "key", {
          get: K,
          configurable: !0
        });
      }
      function ka(C, D) {
        var K = function() {
          pi || (pi = !0, ie("%s: `ref` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://reactjs.org/link/special-props)", D));
        };
        K.isReactWarning = !0, Object.defineProperty(C, "ref", {
          get: K,
          configurable: !0
        });
      }
      function xe(C) {
        if (typeof C.ref == "string" && Ce.current && C.__self && Ce.current.stateNode !== C.__self) {
          var D = ir(Ce.current.type);
          Qn[D] || (ie('Component "%s" contains the string ref "%s". Support for string refs will be removed in a future major release. This case cannot be automatically converted to an arrow function. We ask you to manually fix this case by using useRef() or createRef() instead. Learn more about using refs safely here: https://reactjs.org/link/strict-mode-string-ref', D, C.ref), Qn[D] = !0);
        }
      }
      var it = function(C, D, K, ee, Ee, Ke, He) {
        var ft = {
          // This tag allows us to uniquely identify this as a React Element
          $$typeof: S,
          // Built-in properties that belong on the element
          type: C,
          key: D,
          ref: K,
          props: He,
          // Record the component responsible for creating this element.
          _owner: Ke
        };
        return ft._store = {}, Object.defineProperty(ft._store, "validated", {
          configurable: !1,
          enumerable: !1,
          writable: !0,
          value: !1
        }), Object.defineProperty(ft, "_self", {
          configurable: !1,
          enumerable: !1,
          writable: !1,
          value: ee
        }), Object.defineProperty(ft, "_source", {
          configurable: !1,
          enumerable: !1,
          writable: !1,
          value: Ee
        }), Object.freeze && (Object.freeze(ft.props), Object.freeze(ft)), ft;
      };
      function Rt(C, D, K) {
        var ee, Ee = {}, Ke = null, He = null, ft = null, xt = null;
        if (D != null) {
          br(D) && (He = D.ref, xe(D)), la(D) && (_a(D.key), Ke = "" + D.key), ft = D.__self === void 0 ? null : D.__self, xt = D.__source === void 0 ? null : D.__source;
          for (ee in D)
            dr.call(D, ee) && !pr.hasOwnProperty(ee) && (Ee[ee] = D[ee]);
        }
        var Kt = arguments.length - 2;
        if (Kt === 1)
          Ee.children = K;
        else if (Kt > 1) {
          for (var ln = Array(Kt), un = 0; un < Kt; un++)
            ln[un] = arguments[un + 2];
          Object.freeze && Object.freeze(ln), Ee.children = ln;
        }
        if (C && C.defaultProps) {
          var bt = C.defaultProps;
          for (ee in bt)
            Ee[ee] === void 0 && (Ee[ee] = bt[ee]);
        }
        if (Ke || He) {
          var hn = typeof C == "function" ? C.displayName || C.name || "Unknown" : C;
          Ke && eo(Ee, hn), He && ka(Ee, hn);
        }
        return it(C, Ke, He, ft, xt, Ce.current, Ee);
      }
      function Gt(C, D) {
        var K = it(C.type, D, C.ref, C._self, C._source, C._owner, C.props);
        return K;
      }
      function bn(C, D, K) {
        if (C == null)
          throw new Error("React.cloneElement(...): The argument must be a React element, but you passed " + C + ".");
        var ee, Ee = ye({}, C.props), Ke = C.key, He = C.ref, ft = C._self, xt = C._source, Kt = C._owner;
        if (D != null) {
          br(D) && (He = D.ref, Kt = Ce.current), la(D) && (_a(D.key), Ke = "" + D.key);
          var ln;
          C.type && C.type.defaultProps && (ln = C.type.defaultProps);
          for (ee in D)
            dr.call(D, ee) && !pr.hasOwnProperty(ee) && (D[ee] === void 0 && ln !== void 0 ? Ee[ee] = ln[ee] : Ee[ee] = D[ee]);
        }
        var un = arguments.length - 2;
        if (un === 1)
          Ee.children = K;
        else if (un > 1) {
          for (var bt = Array(un), hn = 0; hn < un; hn++)
            bt[hn] = arguments[hn + 2];
          Ee.children = bt;
        }
        return it(C.type, Ke, He, ft, xt, Kt, Ee);
      }
      function Tn(C) {
        return typeof C == "object" && C !== null && C.$$typeof === S;
      }
      var Rn = ".", vr = ":";
      function gn(C) {
        var D = /[=:]/g, K = {
          "=": "=0",
          ":": "=2"
        }, ee = C.replace(D, function(Ee) {
          return K[Ee];
        });
        return "$" + ee;
      }
      var an = !1, Qt = /\/+/g;
      function Oa(C) {
        return C.replace(Qt, "$&/");
      }
      function Ia(C, D) {
        return typeof C == "object" && C !== null && C.key != null ? (_a(C.key), gn("" + C.key)) : D.toString(36);
      }
      function Ya(C, D, K, ee, Ee) {
        var Ke = typeof C;
        (Ke === "undefined" || Ke === "boolean") && (C = null);
        var He = !1;
        if (C === null)
          He = !0;
        else
          switch (Ke) {
            case "string":
            case "number":
              He = !0;
              break;
            case "object":
              switch (C.$$typeof) {
                case S:
                case T:
                  He = !0;
              }
          }
        if (He) {
          var ft = C, xt = Ee(ft), Kt = ee === "" ? Rn + Ia(ft, 0) : ee;
          if (Wt(xt)) {
            var ln = "";
            Kt != null && (ln = Oa(Kt) + "/"), Ya(xt, D, ln, "", function(Id) {
              return Id;
            });
          } else xt != null && (Tn(xt) && (xt.key && (!ft || ft.key !== xt.key) && _a(xt.key), xt = Gt(
            xt,
            // Keep both the (mapped) and old keys if they differ, just as
            // traverseAllChildren used to do for objects as children
            K + // $FlowFixMe Flow incorrectly thinks React.Portal doesn't have a key
            (xt.key && (!ft || ft.key !== xt.key) ? (
              // $FlowFixMe Flow incorrectly thinks existing element's key can be a number
              // eslint-disable-next-line react-internal/safe-string-coercion
              Oa("" + xt.key) + "/"
            ) : "") + Kt
          )), D.push(xt));
          return 1;
        }
        var un, bt, hn = 0, Hn = ee === "" ? Rn : ee + vr;
        if (Wt(C))
          for (var _l = 0; _l < C.length; _l++)
            un = C[_l], bt = Hn + Ia(un, _l), hn += Ya(un, D, K, bt, Ee);
        else {
          var _s = de(C);
          if (typeof _s == "function") {
            var co = C;
            _s === co.entries && (an || ot("Using Maps as children is not supported. Use an array of keyed ReactElements instead."), an = !0);
            for (var kl = _s.call(co), ks, Bd = 0; !(ks = kl.next()).done; )
              un = ks.value, bt = Hn + Ia(un, Bd++), hn += Ya(un, D, K, bt, Ee);
          } else if (Ke === "object") {
            var Ic = String(C);
            throw new Error("Objects are not valid as a React child (found: " + (Ic === "[object Object]" ? "object with keys {" + Object.keys(C).join(", ") + "}" : Ic) + "). If you meant to render a collection of children, use an array instead.");
          }
        }
        return hn;
      }
      function to(C, D, K) {
        if (C == null)
          return C;
        var ee = [], Ee = 0;
        return Ya(C, ee, "", "", function(Ke) {
          return D.call(K, Ke, Ee++);
        }), ee;
      }
      function Sl(C) {
        var D = 0;
        return to(C, function() {
          D++;
        }), D;
      }
      function El(C, D, K) {
        to(C, function() {
          D.apply(this, arguments);
        }, K);
      }
      function no(C) {
        return to(C, function(D) {
          return D;
        }) || [];
      }
      function Cl(C) {
        if (!Tn(C))
          throw new Error("React.Children.only expected to receive a single React element child.");
        return C;
      }
      function Di(C) {
        var D = {
          $$typeof: A,
          // As a workaround to support multiple concurrent renderers, we categorize
          // some renderers as primary and others as secondary. We only expect
          // there to be two concurrent renderers at most: React Native (primary) and
          // Fabric (secondary); React DOM (primary) and React ART (secondary).
          // Secondary renderers store their context values on separate fields.
          _currentValue: C,
          _currentValue2: C,
          // Used to track how many concurrent renderers this context currently
          // supports within in a single renderer. Such as parallel server rendering.
          _threadCount: 0,
          // These are circular
          Provider: null,
          Consumer: null,
          // Add these to use same hidden class in VM as ServerContext
          _defaultValue: null,
          _globalName: null
        };
        D.Provider = {
          $$typeof: z,
          _context: D
        };
        var K = !1, ee = !1, Ee = !1;
        {
          var Ke = {
            $$typeof: A,
            _context: D
          };
          Object.defineProperties(Ke, {
            Provider: {
              get: function() {
                return ee || (ee = !0, ie("Rendering <Context.Consumer.Provider> is not supported and will be removed in a future major release. Did you mean to render <Context.Provider> instead?")), D.Provider;
              },
              set: function(He) {
                D.Provider = He;
              }
            },
            _currentValue: {
              get: function() {
                return D._currentValue;
              },
              set: function(He) {
                D._currentValue = He;
              }
            },
            _currentValue2: {
              get: function() {
                return D._currentValue2;
              },
              set: function(He) {
                D._currentValue2 = He;
              }
            },
            _threadCount: {
              get: function() {
                return D._threadCount;
              },
              set: function(He) {
                D._threadCount = He;
              }
            },
            Consumer: {
              get: function() {
                return K || (K = !0, ie("Rendering <Context.Consumer.Consumer> is not supported and will be removed in a future major release. Did you mean to render <Context.Consumer> instead?")), D.Consumer;
              }
            },
            displayName: {
              get: function() {
                return D.displayName;
              },
              set: function(He) {
                Ee || (ot("Setting `displayName` on Context.Consumer has no effect. You should set it directly on the context with Context.displayName = '%s'.", He), Ee = !0);
              }
            }
          }), D.Consumer = Ke;
        }
        return D._currentRenderer = null, D._currentRenderer2 = null, D;
      }
      var Da = -1, Tr = 0, Na = 1, ua = 2;
      function Ni(C) {
        if (C._status === Da) {
          var D = C._result, K = D();
          if (K.then(function(Ke) {
            if (C._status === Tr || C._status === Da) {
              var He = C;
              He._status = Na, He._result = Ke;
            }
          }, function(Ke) {
            if (C._status === Tr || C._status === Da) {
              var He = C;
              He._status = ua, He._result = Ke;
            }
          }), C._status === Da) {
            var ee = C;
            ee._status = Tr, ee._result = K;
          }
        }
        if (C._status === Na) {
          var Ee = C._result;
          return Ee === void 0 && ie(`lazy: Expected the result of a dynamic import() call. Instead received: %s

Your code should look like: 
  const MyComponent = lazy(() => import('./MyComponent'))

Did you accidentally put curly braces around the import?`, Ee), "default" in Ee || ie(`lazy: Expected the result of a dynamic import() call. Instead received: %s

Your code should look like: 
  const MyComponent = lazy(() => import('./MyComponent'))`, Ee), Ee.default;
        } else
          throw C._result;
      }
      function Ai(C) {
        var D = {
          // We use these fields to store the result.
          _status: Da,
          _result: C
        }, K = {
          $$typeof: M,
          _payload: D,
          _init: Ni
        };
        {
          var ee, Ee;
          Object.defineProperties(K, {
            defaultProps: {
              configurable: !0,
              get: function() {
                return ee;
              },
              set: function(Ke) {
                ie("React.lazy(...): It is not supported to assign `defaultProps` to a lazy component import. Either specify them where the component is defined, or create a wrapping component around it."), ee = Ke, Object.defineProperty(K, "defaultProps", {
                  enumerable: !0
                });
              }
            },
            propTypes: {
              configurable: !0,
              get: function() {
                return Ee;
              },
              set: function(Ke) {
                ie("React.lazy(...): It is not supported to assign `propTypes` to a lazy component import. Either specify them where the component is defined, or create a wrapping component around it."), Ee = Ke, Object.defineProperty(K, "propTypes", {
                  enumerable: !0
                });
              }
            }
          });
        }
        return K;
      }
      function ro(C) {
        C != null && C.$$typeof === B ? ie("forwardRef requires a render function but received a `memo` component. Instead of forwardRef(memo(...)), use memo(forwardRef(...)).") : typeof C != "function" ? ie("forwardRef requires a render function but was given %s.", C === null ? "null" : typeof C) : C.length !== 0 && C.length !== 2 && ie("forwardRef render functions accept exactly two parameters: props and ref. %s", C.length === 1 ? "Did you forget to use the ref parameter?" : "Any additional parameter will be undefined."), C != null && (C.defaultProps != null || C.propTypes != null) && ie("forwardRef render functions do not support propTypes or defaultProps. Did you accidentally pass a React component?");
        var D = {
          $$typeof: F,
          render: C
        };
        {
          var K;
          Object.defineProperty(D, "displayName", {
            enumerable: !1,
            configurable: !0,
            get: function() {
              return K;
            },
            set: function(ee) {
              K = ee, !C.name && !C.displayName && (C.displayName = ee);
            }
          });
        }
        return D;
      }
      var N;
      N = Symbol.for("react.module.reference");
      function fe(C) {
        return !!(typeof C == "string" || typeof C == "function" || C === _ || C === L || pt || C === g || C === U || C === te || Pe || C === j || ge || je || Qe || typeof C == "object" && C !== null && (C.$$typeof === M || C.$$typeof === B || C.$$typeof === z || C.$$typeof === A || C.$$typeof === F || // This needs to include all possible module reference object
        // types supported by any Flight configuration anywhere since
        // we don't know which Flight build this will end up being used
        // with.
        C.$$typeof === N || C.getModuleId !== void 0));
      }
      function Ae(C, D) {
        fe(C) || ie("memo: The first argument must be a component. Instead received: %s", C === null ? "null" : typeof C);
        var K = {
          $$typeof: B,
          type: C,
          compare: D === void 0 ? null : D
        };
        {
          var ee;
          Object.defineProperty(K, "displayName", {
            enumerable: !1,
            configurable: !0,
            get: function() {
              return ee;
            },
            set: function(Ee) {
              ee = Ee, !C.name && !C.displayName && (C.displayName = Ee);
            }
          });
        }
        return K;
      }
      function Ue() {
        var C = ue.current;
        return C === null && ie(`Invalid hook call. Hooks can only be called inside of the body of a function component. This could happen for one of the following reasons:
1. You might have mismatching versions of React and the renderer (such as React DOM)
2. You might be breaking the Rules of Hooks
3. You might have more than one copy of React in the same app
See https://reactjs.org/link/invalid-hook-call for tips about how to debug and fix this problem.`), C;
      }
      function kt(C) {
        var D = Ue();
        if (C._context !== void 0) {
          var K = C._context;
          K.Consumer === C ? ie("Calling useContext(Context.Consumer) is not supported, may cause bugs, and will be removed in a future major release. Did you mean to call useContext(Context) instead?") : K.Provider === C && ie("Calling useContext(Context.Provider) is not supported. Did you mean to call useContext(Context) instead?");
        }
        return D.useContext(C);
      }
      function yt(C) {
        var D = Ue();
        return D.useState(C);
      }
      function Nt(C, D, K) {
        var ee = Ue();
        return ee.useReducer(C, D, K);
      }
      function wt(C) {
        var D = Ue();
        return D.useRef(C);
      }
      function jn(C, D) {
        var K = Ue();
        return K.useEffect(C, D);
      }
      function Sn(C, D) {
        var K = Ue();
        return K.useInsertionEffect(C, D);
      }
      function wn(C, D) {
        var K = Ue();
        return K.useLayoutEffect(C, D);
      }
      function $r(C, D) {
        var K = Ue();
        return K.useCallback(C, D);
      }
      function vi(C, D) {
        var K = Ue();
        return K.useMemo(C, D);
      }
      function qt(C, D, K) {
        var ee = Ue();
        return ee.useImperativeHandle(C, D, K);
      }
      function Dn(C, D) {
        {
          var K = Ue();
          return K.useDebugValue(C, D);
        }
      }
      function Et() {
        var C = Ue();
        return C.useTransition();
      }
      function Mi(C) {
        var D = Ue();
        return D.useDeferredValue(C);
      }
      function ao() {
        var C = Ue();
        return C.useId();
      }
      function jc(C, D, K) {
        var ee = Ue();
        return ee.useSyncExternalStore(C, D, K);
      }
      var io = 0, No, sa, Cs, Yr, bs, Hc, Vc;
      function oo() {
      }
      oo.__reactDisabledLog = !0;
      function Ao() {
        {
          if (io === 0) {
            No = console.log, sa = console.info, Cs = console.warn, Yr = console.error, bs = console.group, Hc = console.groupCollapsed, Vc = console.groupEnd;
            var C = {
              configurable: !0,
              enumerable: !0,
              value: oo,
              writable: !0
            };
            Object.defineProperties(console, {
              info: C,
              log: C,
              warn: C,
              error: C,
              group: C,
              groupCollapsed: C,
              groupEnd: C
            });
          }
          io++;
        }
      }
      function ca() {
        {
          if (io--, io === 0) {
            var C = {
              configurable: !0,
              enumerable: !0,
              writable: !0
            };
            Object.defineProperties(console, {
              log: ye({}, C, {
                value: No
              }),
              info: ye({}, C, {
                value: sa
              }),
              warn: ye({}, C, {
                value: Cs
              }),
              error: ye({}, C, {
                value: Yr
              }),
              group: ye({}, C, {
                value: bs
              }),
              groupCollapsed: ye({}, C, {
                value: Hc
              }),
              groupEnd: ye({}, C, {
                value: Vc
              })
            });
          }
          io < 0 && ie("disabledDepth fell below zero. This is a bug in React. Please file an issue.");
        }
      }
      var Li = vt.ReactCurrentDispatcher, Mo;
      function hu(C, D, K) {
        {
          if (Mo === void 0)
            try {
              throw Error();
            } catch (Ee) {
              var ee = Ee.stack.trim().match(/\n( *(at )?)/);
              Mo = ee && ee[1] || "";
            }
          return `
` + Mo + C;
        }
      }
      var lo = !1, bl;
      {
        var Tl = typeof WeakMap == "function" ? WeakMap : Map;
        bl = new Tl();
      }
      function Lo(C, D) {
        if (!C || lo)
          return "";
        {
          var K = bl.get(C);
          if (K !== void 0)
            return K;
        }
        var ee;
        lo = !0;
        var Ee = Error.prepareStackTrace;
        Error.prepareStackTrace = void 0;
        var Ke;
        Ke = Li.current, Li.current = null, Ao();
        try {
          if (D) {
            var He = function() {
              throw Error();
            };
            if (Object.defineProperty(He.prototype, "props", {
              set: function() {
                throw Error();
              }
            }), typeof Reflect == "object" && Reflect.construct) {
              try {
                Reflect.construct(He, []);
              } catch (Hn) {
                ee = Hn;
              }
              Reflect.construct(C, [], He);
            } else {
              try {
                He.call();
              } catch (Hn) {
                ee = Hn;
              }
              C.call(He.prototype);
            }
          } else {
            try {
              throw Error();
            } catch (Hn) {
              ee = Hn;
            }
            C();
          }
        } catch (Hn) {
          if (Hn && ee && typeof Hn.stack == "string") {
            for (var ft = Hn.stack.split(`
`), xt = ee.stack.split(`
`), Kt = ft.length - 1, ln = xt.length - 1; Kt >= 1 && ln >= 0 && ft[Kt] !== xt[ln]; )
              ln--;
            for (; Kt >= 1 && ln >= 0; Kt--, ln--)
              if (ft[Kt] !== xt[ln]) {
                if (Kt !== 1 || ln !== 1)
                  do
                    if (Kt--, ln--, ln < 0 || ft[Kt] !== xt[ln]) {
                      var un = `
` + ft[Kt].replace(" at new ", " at ");
                      return C.displayName && un.includes("<anonymous>") && (un = un.replace("<anonymous>", C.displayName)), typeof C == "function" && bl.set(C, un), un;
                    }
                  while (Kt >= 1 && ln >= 0);
                break;
              }
          }
        } finally {
          lo = !1, Li.current = Ke, ca(), Error.prepareStackTrace = Ee;
        }
        var bt = C ? C.displayName || C.name : "", hn = bt ? hu(bt) : "";
        return typeof C == "function" && bl.set(C, hn), hn;
      }
      function Ts(C, D, K) {
        return Lo(C, !1);
      }
      function Rs(C) {
        var D = C.prototype;
        return !!(D && D.isReactComponent);
      }
      function Pt(C, D, K) {
        if (C == null)
          return "";
        if (typeof C == "function")
          return Lo(C, Rs(C));
        if (typeof C == "string")
          return hu(C);
        switch (C) {
          case U:
            return hu("Suspense");
          case te:
            return hu("SuspenseList");
        }
        if (typeof C == "object")
          switch (C.$$typeof) {
            case F:
              return Ts(C.render);
            case B:
              return Pt(C.type, D, K);
            case M: {
              var ee = C, Ee = ee._payload, Ke = ee._init;
              try {
                return Pt(Ke(Ee), D, K);
              } catch {
              }
            }
          }
        return "";
      }
      var ws = {}, mu = vt.ReactDebugCurrentFrame;
      function $t(C) {
        if (C) {
          var D = C._owner, K = Pt(C.type, C._source, D ? D.type : null);
          mu.setExtraStackFrame(K);
        } else
          mu.setExtraStackFrame(null);
      }
      function Bc(C, D, K, ee, Ee) {
        {
          var Ke = Function.call.bind(dr);
          for (var He in C)
            if (Ke(C, He)) {
              var ft = void 0;
              try {
                if (typeof C[He] != "function") {
                  var xt = Error((ee || "React class") + ": " + K + " type `" + He + "` is invalid; it must be a function, usually from the `prop-types` package, but received `" + typeof C[He] + "`.This often happens because of typos such as `PropTypes.function` instead of `PropTypes.func`.");
                  throw xt.name = "Invariant Violation", xt;
                }
                ft = C[He](D, He, ee, K, null, "SECRET_DO_NOT_PASS_THIS_OR_YOU_WILL_BE_FIRED");
              } catch (Kt) {
                ft = Kt;
              }
              ft && !(ft instanceof Error) && ($t(Ee), ie("%s: type specification of %s `%s` is invalid; the type checker function must return `null` or an `Error` but returned a %s. You may have forgotten to pass an argument to the type checker creator (arrayOf, instanceOf, objectOf, oneOf, oneOfType, and shape all require an argument).", ee || "React class", K, He, typeof ft), $t(null)), ft instanceof Error && !(ft.message in ws) && (ws[ft.message] = !0, $t(Ee), ie("Failed %s type: %s", K, ft.message), $t(null));
            }
        }
      }
      function zi(C) {
        if (C) {
          var D = C._owner, K = Pt(C.type, C._source, D ? D.type : null);
          x(K);
        } else
          x(null);
      }
      var ht;
      ht = !1;
      function Rl() {
        if (Ce.current) {
          var C = ir(Ce.current.type);
          if (C)
            return `

Check the render method of \`` + C + "`.";
        }
        return "";
      }
      function hr(C) {
        if (C !== void 0) {
          var D = C.fileName.replace(/^.*[\\\/]/, ""), K = C.lineNumber;
          return `

Check your code at ` + D + ":" + K + ".";
        }
        return "";
      }
      function fa(C) {
        return C != null ? hr(C.__source) : "";
      }
      var Wr = {};
      function Ui(C) {
        var D = Rl();
        if (!D) {
          var K = typeof C == "string" ? C : C.displayName || C.name;
          K && (D = `

Check the top-level render call using <` + K + ">.");
        }
        return D;
      }
      function zn(C, D) {
        if (!(!C._store || C._store.validated || C.key != null)) {
          C._store.validated = !0;
          var K = Ui(D);
          if (!Wr[K]) {
            Wr[K] = !0;
            var ee = "";
            C && C._owner && C._owner !== Ce.current && (ee = " It was passed a child from " + ir(C._owner.type) + "."), zi(C), ie('Each child in a list should have a unique "key" prop.%s%s See https://reactjs.org/link/warning-keys for more information.', K, ee), zi(null);
          }
        }
      }
      function on(C, D) {
        if (typeof C == "object") {
          if (Wt(C))
            for (var K = 0; K < C.length; K++) {
              var ee = C[K];
              Tn(ee) && zn(ee, D);
            }
          else if (Tn(C))
            C._store && (C._store.validated = !0);
          else if (C) {
            var Ee = de(C);
            if (typeof Ee == "function" && Ee !== C.entries)
              for (var Ke = Ee.call(C), He; !(He = Ke.next()).done; )
                Tn(He.value) && zn(He.value, D);
          }
        }
      }
      function hi(C) {
        {
          var D = C.type;
          if (D == null || typeof D == "string")
            return;
          var K;
          if (typeof D == "function")
            K = D.propTypes;
          else if (typeof D == "object" && (D.$$typeof === F || // Note: Memo only checks outer props here.
          // Inner props are checked in the reconciler.
          D.$$typeof === B))
            K = D.propTypes;
          else
            return;
          if (K) {
            var ee = ir(D);
            Bc(K, C.props, "prop", ee, C);
          } else if (D.PropTypes !== void 0 && !ht) {
            ht = !0;
            var Ee = ir(D);
            ie("Component %s declared `PropTypes` instead of `propTypes`. Did you misspell the property assignment?", Ee || "Unknown");
          }
          typeof D.getDefaultProps == "function" && !D.getDefaultProps.isReactClassApproved && ie("getDefaultProps is only used on classic React.createClass definitions. Use a static property named `defaultProps` instead.");
        }
      }
      function Wa(C) {
        {
          for (var D = Object.keys(C.props), K = 0; K < D.length; K++) {
            var ee = D[K];
            if (ee !== "children" && ee !== "key") {
              zi(C), ie("Invalid prop `%s` supplied to `React.Fragment`. React.Fragment can only have `key` and `children` props.", ee), zi(null);
              break;
            }
          }
          C.ref !== null && (zi(C), ie("Invalid attribute `ref` supplied to `React.Fragment`."), zi(null));
        }
      }
      function Fr(C, D, K) {
        var ee = fe(C);
        if (!ee) {
          var Ee = "";
          (C === void 0 || typeof C == "object" && C !== null && Object.keys(C).length === 0) && (Ee += " You likely forgot to export your component from the file it's defined in, or you might have mixed up default and named imports.");
          var Ke = fa(D);
          Ke ? Ee += Ke : Ee += Rl();
          var He;
          C === null ? He = "null" : Wt(C) ? He = "array" : C !== void 0 && C.$$typeof === S ? (He = "<" + (ir(C.type) || "Unknown") + " />", Ee = " Did you accidentally export a JSX literal instead of a component?") : He = typeof C, ie("React.createElement: type is invalid -- expected a string (for built-in components) or a class/function (for composite components) but got: %s.%s", He, Ee);
        }
        var ft = Rt.apply(this, arguments);
        if (ft == null)
          return ft;
        if (ee)
          for (var xt = 2; xt < arguments.length; xt++)
            on(arguments[xt], C);
        return C === _ ? Wa(ft) : hi(ft), ft;
      }
      var Gr = !1;
      function Vd(C) {
        var D = Fr.bind(null, C);
        return D.type = C, Gr || (Gr = !0, ot("React.createFactory() is deprecated and will be removed in a future major release. Consider using JSX or use React.createElement() directly instead.")), Object.defineProperty(D, "type", {
          enumerable: !1,
          get: function() {
            return ot("Factory.type is deprecated. Access the class directly before passing it to createFactory."), Object.defineProperty(this, "type", {
              value: C
            }), C;
          }
        }), D;
      }
      function yu(C, D, K) {
        for (var ee = bn.apply(this, arguments), Ee = 2; Ee < arguments.length; Ee++)
          on(arguments[Ee], ee.type);
        return hi(ee), ee;
      }
      function wl(C, D) {
        var K = q.transition;
        q.transition = {};
        var ee = q.transition;
        q.transition._updatedFibers = /* @__PURE__ */ new Set();
        try {
          C();
        } finally {
          if (q.transition = K, K === null && ee._updatedFibers) {
            var Ee = ee._updatedFibers.size;
            Ee > 10 && ot("Detected a large number of updates inside startTransition. If this is due to a subscription please re-write it to use React provided hooks. Otherwise concurrent mode guarantees are off the table."), ee._updatedFibers.clear();
          }
        }
      }
      var gu = !1, Su = null;
      function xl(C) {
        if (Su === null)
          try {
            var D = ("require" + Math.random()).slice(0, 7), K = u && u[D];
            Su = K.call(u, "timers").setImmediate;
          } catch {
            Su = function(Ee) {
              gu === !1 && (gu = !0, typeof MessageChannel > "u" && ie("This browser does not have a MessageChannel implementation, so enqueuing tasks via await act(async () => ...) will fail. Please file an issue at https://github.com/facebook/react/issues if you encounter this warning."));
              var Ke = new MessageChannel();
              Ke.port1.onmessage = Ee, Ke.port2.postMessage(void 0);
            };
          }
        return Su(C);
      }
      var Ga = 0, Qa = !1;
      function zo(C) {
        {
          var D = Ga;
          Ga++, se.current === null && (se.current = []);
          var K = se.isBatchingLegacy, ee;
          try {
            if (se.isBatchingLegacy = !0, ee = C(), !K && se.didScheduleLegacyUpdate) {
              var Ee = se.current;
              Ee !== null && (se.didScheduleLegacyUpdate = !1, so(Ee));
            }
          } catch (bt) {
            throw uo(D), bt;
          } finally {
            se.isBatchingLegacy = K;
          }
          if (ee !== null && typeof ee == "object" && typeof ee.then == "function") {
            var Ke = ee, He = !1, ft = {
              then: function(bt, hn) {
                He = !0, Ke.then(function(Hn) {
                  uo(D), Ga === 0 ? Eu(Hn, bt, hn) : bt(Hn);
                }, function(Hn) {
                  uo(D), hn(Hn);
                });
              }
            };
            return !Qa && typeof Promise < "u" && Promise.resolve().then(function() {
            }).then(function() {
              He || (Qa = !0, ie("You called act(async () => ...) without await. This could lead to unexpected testing behaviour, interleaving multiple act calls and mixing their scopes. You should - await act(async () => ...);"));
            }), ft;
          } else {
            var xt = ee;
            if (uo(D), Ga === 0) {
              var Kt = se.current;
              Kt !== null && (so(Kt), se.current = null);
              var ln = {
                then: function(bt, hn) {
                  se.current === null ? (se.current = [], Eu(xt, bt, hn)) : bt(xt);
                }
              };
              return ln;
            } else {
              var un = {
                then: function(bt, hn) {
                  bt(xt);
                }
              };
              return un;
            }
          }
        }
      }
      function uo(C) {
        C !== Ga - 1 && ie("You seem to have overlapping act() calls, this is not supported. Be sure to await previous act() calls before making a new one. "), Ga = C;
      }
      function Eu(C, D, K) {
        {
          var ee = se.current;
          if (ee !== null)
            try {
              so(ee), xl(function() {
                ee.length === 0 ? (se.current = null, D(C)) : Eu(C, D, K);
              });
            } catch (Ee) {
              K(Ee);
            }
          else
            D(C);
        }
      }
      var Uo = !1;
      function so(C) {
        if (!Uo) {
          Uo = !0;
          var D = 0;
          try {
            for (; D < C.length; D++) {
              var K = C[D];
              do
                K = K(!0);
              while (K !== null);
            }
            C.length = 0;
          } catch (ee) {
            throw C = C.slice(D + 1), ee;
          } finally {
            Uo = !1;
          }
        }
      }
      var Cu = Fr, xs = yu, qa = Vd, bu = {
        map: to,
        forEach: El,
        count: Sl,
        toArray: no,
        only: Cl
      };
      f.Children = bu, f.Component = be, f.Fragment = _, f.Profiler = L, f.PureComponent = et, f.StrictMode = g, f.Suspense = U, f.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = vt, f.act = zo, f.cloneElement = xs, f.createContext = Di, f.createElement = Cu, f.createFactory = qa, f.createRef = Ht, f.forwardRef = ro, f.isValidElement = Tn, f.lazy = Ai, f.memo = Ae, f.startTransition = wl, f.unstable_act = zo, f.useCallback = $r, f.useContext = kt, f.useDebugValue = Dn, f.useDeferredValue = Mi, f.useEffect = jn, f.useId = ao, f.useImperativeHandle = qt, f.useInsertionEffect = Sn, f.useLayoutEffect = wn, f.useMemo = vi, f.useReducer = Nt, f.useRef = wt, f.useState = yt, f.useSyncExternalStore = jc, f.useTransition = Et, f.version = y, typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u" && typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop == "function" && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop(new Error());
    }();
  }(Gv, Gv.exports)), Gv.exports;
}
var xN = {};
xN.NODE_ENV === "production" ? tC.exports = RN() : tC.exports = wN();
var Vt = tC.exports;
const _e = /* @__PURE__ */ ew(Vt), cR = /* @__PURE__ */ TN({
  __proto__: null,
  default: _e
}, [Vt]);
var nC = { exports: {} }, si = {}, Ky = { exports: {} }, VE = {};
/**
 * @license React
 * scheduler.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var fR;
function _N() {
  return fR || (fR = 1, function(u) {
    function f(ie, Ie) {
      var ke = ie.length;
      ie.push(Ie);
      e: for (; 0 < ke; ) {
        var k = ke - 1 >>> 1, I = ie[k];
        if (0 < S(I, Ie)) ie[k] = Ie, ie[ke] = I, ke = k;
        else break e;
      }
    }
    function v(ie) {
      return ie.length === 0 ? null : ie[0];
    }
    function y(ie) {
      if (ie.length === 0) return null;
      var Ie = ie[0], ke = ie.pop();
      if (ke !== Ie) {
        ie[0] = ke;
        e: for (var k = 0, I = ie.length, ye = I >>> 1; k < ye; ) {
          var Re = 2 * (k + 1) - 1, be = ie[Re], Le = Re + 1, ze = ie[Le];
          if (0 > S(be, ke)) Le < I && 0 > S(ze, be) ? (ie[k] = ze, ie[Le] = ke, k = Le) : (ie[k] = be, ie[Re] = ke, k = Re);
          else if (Le < I && 0 > S(ze, ke)) ie[k] = ze, ie[Le] = ke, k = Le;
          else break e;
        }
      }
      return Ie;
    }
    function S(ie, Ie) {
      var ke = ie.sortIndex - Ie.sortIndex;
      return ke !== 0 ? ke : ie.id - Ie.id;
    }
    if (typeof performance == "object" && typeof performance.now == "function") {
      var T = performance;
      u.unstable_now = function() {
        return T.now();
      };
    } else {
      var _ = Date, g = _.now();
      u.unstable_now = function() {
        return _.now() - g;
      };
    }
    var L = [], z = [], A = 1, F = null, U = 3, te = !1, B = !1, M = !1, j = typeof setTimeout == "function" ? setTimeout : null, ce = typeof clearTimeout == "function" ? clearTimeout : null, De = typeof setImmediate < "u" ? setImmediate : null;
    typeof navigator < "u" && navigator.scheduling !== void 0 && navigator.scheduling.isInputPending !== void 0 && navigator.scheduling.isInputPending.bind(navigator.scheduling);
    function de(ie) {
      for (var Ie = v(z); Ie !== null; ) {
        if (Ie.callback === null) y(z);
        else if (Ie.startTime <= ie) y(z), Ie.sortIndex = Ie.expirationTime, f(L, Ie);
        else break;
        Ie = v(z);
      }
    }
    function ue(ie) {
      if (M = !1, de(ie), !B) if (v(L) !== null) B = !0, vt(q);
      else {
        var Ie = v(z);
        Ie !== null && ot(ue, Ie.startTime - ie);
      }
    }
    function q(ie, Ie) {
      B = !1, M && (M = !1, ce(Ge), Ge = -1), te = !0;
      var ke = U;
      try {
        for (de(Ie), F = v(L); F !== null && (!(F.expirationTime > Ie) || ie && !ge()); ) {
          var k = F.callback;
          if (typeof k == "function") {
            F.callback = null, U = F.priorityLevel;
            var I = k(F.expirationTime <= Ie);
            Ie = u.unstable_now(), typeof I == "function" ? F.callback = I : F === v(L) && y(L), de(Ie);
          } else y(L);
          F = v(L);
        }
        if (F !== null) var ye = !0;
        else {
          var Re = v(z);
          Re !== null && ot(ue, Re.startTime - Ie), ye = !1;
        }
        return ye;
      } finally {
        F = null, U = ke, te = !1;
      }
    }
    var se = !1, Ce = null, Ge = -1, _t = 5, x = -1;
    function ge() {
      return !(u.unstable_now() - x < _t);
    }
    function je() {
      if (Ce !== null) {
        var ie = u.unstable_now();
        x = ie;
        var Ie = !0;
        try {
          Ie = Ce(!0, ie);
        } finally {
          Ie ? Qe() : (se = !1, Ce = null);
        }
      } else se = !1;
    }
    var Qe;
    if (typeof De == "function") Qe = function() {
      De(je);
    };
    else if (typeof MessageChannel < "u") {
      var Pe = new MessageChannel(), pt = Pe.port2;
      Pe.port1.onmessage = je, Qe = function() {
        pt.postMessage(null);
      };
    } else Qe = function() {
      j(je, 0);
    };
    function vt(ie) {
      Ce = ie, se || (se = !0, Qe());
    }
    function ot(ie, Ie) {
      Ge = j(function() {
        ie(u.unstable_now());
      }, Ie);
    }
    u.unstable_IdlePriority = 5, u.unstable_ImmediatePriority = 1, u.unstable_LowPriority = 4, u.unstable_NormalPriority = 3, u.unstable_Profiling = null, u.unstable_UserBlockingPriority = 2, u.unstable_cancelCallback = function(ie) {
      ie.callback = null;
    }, u.unstable_continueExecution = function() {
      B || te || (B = !0, vt(q));
    }, u.unstable_forceFrameRate = function(ie) {
      0 > ie || 125 < ie ? console.error("forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported") : _t = 0 < ie ? Math.floor(1e3 / ie) : 5;
    }, u.unstable_getCurrentPriorityLevel = function() {
      return U;
    }, u.unstable_getFirstCallbackNode = function() {
      return v(L);
    }, u.unstable_next = function(ie) {
      switch (U) {
        case 1:
        case 2:
        case 3:
          var Ie = 3;
          break;
        default:
          Ie = U;
      }
      var ke = U;
      U = Ie;
      try {
        return ie();
      } finally {
        U = ke;
      }
    }, u.unstable_pauseExecution = function() {
    }, u.unstable_requestPaint = function() {
    }, u.unstable_runWithPriority = function(ie, Ie) {
      switch (ie) {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
          break;
        default:
          ie = 3;
      }
      var ke = U;
      U = ie;
      try {
        return Ie();
      } finally {
        U = ke;
      }
    }, u.unstable_scheduleCallback = function(ie, Ie, ke) {
      var k = u.unstable_now();
      switch (typeof ke == "object" && ke !== null ? (ke = ke.delay, ke = typeof ke == "number" && 0 < ke ? k + ke : k) : ke = k, ie) {
        case 1:
          var I = -1;
          break;
        case 2:
          I = 250;
          break;
        case 5:
          I = 1073741823;
          break;
        case 4:
          I = 1e4;
          break;
        default:
          I = 5e3;
      }
      return I = ke + I, ie = { id: A++, callback: Ie, priorityLevel: ie, startTime: ke, expirationTime: I, sortIndex: -1 }, ke > k ? (ie.sortIndex = ke, f(z, ie), v(L) === null && ie === v(z) && (M ? (ce(Ge), Ge = -1) : M = !0, ot(ue, ke - k))) : (ie.sortIndex = I, f(L, ie), B || te || (B = !0, vt(q))), ie;
    }, u.unstable_shouldYield = ge, u.unstable_wrapCallback = function(ie) {
      var Ie = U;
      return function() {
        var ke = U;
        U = Ie;
        try {
          return ie.apply(this, arguments);
        } finally {
          U = ke;
        }
      };
    };
  }(VE)), VE;
}
var BE = {}, dR;
function kN() {
  return dR || (dR = 1, function(u) {
    var f = {};
    /**
     * @license React
     * scheduler.development.js
     *
     * Copyright (c) Facebook, Inc. and its affiliates.
     *
     * This source code is licensed under the MIT license found in the
     * LICENSE file in the root directory of this source tree.
     */
    f.NODE_ENV !== "production" && function() {
      typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u" && typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart == "function" && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart(new Error());
      var v = !1, y = 5;
      function S(xe, it) {
        var Rt = xe.length;
        xe.push(it), g(xe, it, Rt);
      }
      function T(xe) {
        return xe.length === 0 ? null : xe[0];
      }
      function _(xe) {
        if (xe.length === 0)
          return null;
        var it = xe[0], Rt = xe.pop();
        return Rt !== it && (xe[0] = Rt, L(xe, Rt, 0)), it;
      }
      function g(xe, it, Rt) {
        for (var Gt = Rt; Gt > 0; ) {
          var bn = Gt - 1 >>> 1, Tn = xe[bn];
          if (z(Tn, it) > 0)
            xe[bn] = it, xe[Gt] = Tn, Gt = bn;
          else
            return;
        }
      }
      function L(xe, it, Rt) {
        for (var Gt = Rt, bn = xe.length, Tn = bn >>> 1; Gt < Tn; ) {
          var Rn = (Gt + 1) * 2 - 1, vr = xe[Rn], gn = Rn + 1, an = xe[gn];
          if (z(vr, it) < 0)
            gn < bn && z(an, vr) < 0 ? (xe[Gt] = an, xe[gn] = it, Gt = gn) : (xe[Gt] = vr, xe[Rn] = it, Gt = Rn);
          else if (gn < bn && z(an, it) < 0)
            xe[Gt] = an, xe[gn] = it, Gt = gn;
          else
            return;
        }
      }
      function z(xe, it) {
        var Rt = xe.sortIndex - it.sortIndex;
        return Rt !== 0 ? Rt : xe.id - it.id;
      }
      var A = 1, F = 2, U = 3, te = 4, B = 5;
      function M(xe, it) {
      }
      var j = typeof performance == "object" && typeof performance.now == "function";
      if (j) {
        var ce = performance;
        u.unstable_now = function() {
          return ce.now();
        };
      } else {
        var De = Date, de = De.now();
        u.unstable_now = function() {
          return De.now() - de;
        };
      }
      var ue = 1073741823, q = -1, se = 250, Ce = 5e3, Ge = 1e4, _t = ue, x = [], ge = [], je = 1, Qe = null, Pe = U, pt = !1, vt = !1, ot = !1, ie = typeof setTimeout == "function" ? setTimeout : null, Ie = typeof clearTimeout == "function" ? clearTimeout : null, ke = typeof setImmediate < "u" ? setImmediate : null;
      typeof navigator < "u" && navigator.scheduling !== void 0 && navigator.scheduling.isInputPending !== void 0 && navigator.scheduling.isInputPending.bind(navigator.scheduling);
      function k(xe) {
        for (var it = T(ge); it !== null; ) {
          if (it.callback === null)
            _(ge);
          else if (it.startTime <= xe)
            _(ge), it.sortIndex = it.expirationTime, S(x, it);
          else
            return;
          it = T(ge);
        }
      }
      function I(xe) {
        if (ot = !1, k(xe), !vt)
          if (T(x) !== null)
            vt = !0, Qn(ye);
          else {
            var it = T(ge);
            it !== null && br(I, it.startTime - xe);
          }
      }
      function ye(xe, it) {
        vt = !1, ot && (ot = !1, la()), pt = !0;
        var Rt = Pe;
        try {
          var Gt;
          if (!v) return Re(xe, it);
        } finally {
          Qe = null, Pe = Rt, pt = !1;
        }
      }
      function Re(xe, it) {
        var Rt = it;
        for (k(Rt), Qe = T(x); Qe !== null && !(Qe.expirationTime > Rt && (!xe || di())); ) {
          var Gt = Qe.callback;
          if (typeof Gt == "function") {
            Qe.callback = null, Pe = Qe.priorityLevel;
            var bn = Qe.expirationTime <= Rt, Tn = Gt(bn);
            Rt = u.unstable_now(), typeof Tn == "function" ? Qe.callback = Tn : Qe === T(x) && _(x), k(Rt);
          } else
            _(x);
          Qe = T(x);
        }
        if (Qe !== null)
          return !0;
        var Rn = T(ge);
        return Rn !== null && br(I, Rn.startTime - Rt), !1;
      }
      function be(xe, it) {
        switch (xe) {
          case A:
          case F:
          case U:
          case te:
          case B:
            break;
          default:
            xe = U;
        }
        var Rt = Pe;
        Pe = xe;
        try {
          return it();
        } finally {
          Pe = Rt;
        }
      }
      function Le(xe) {
        var it;
        switch (Pe) {
          case A:
          case F:
          case U:
            it = U;
            break;
          default:
            it = Pe;
            break;
        }
        var Rt = Pe;
        Pe = it;
        try {
          return xe();
        } finally {
          Pe = Rt;
        }
      }
      function ze(xe) {
        var it = Pe;
        return function() {
          var Rt = Pe;
          Pe = it;
          try {
            return xe.apply(this, arguments);
          } finally {
            Pe = Rt;
          }
        };
      }
      function we(xe, it, Rt) {
        var Gt = u.unstable_now(), bn;
        if (typeof Rt == "object" && Rt !== null) {
          var Tn = Rt.delay;
          typeof Tn == "number" && Tn > 0 ? bn = Gt + Tn : bn = Gt;
        } else
          bn = Gt;
        var Rn;
        switch (xe) {
          case A:
            Rn = q;
            break;
          case F:
            Rn = se;
            break;
          case B:
            Rn = _t;
            break;
          case te:
            Rn = Ge;
            break;
          case U:
          default:
            Rn = Ce;
            break;
        }
        var vr = bn + Rn, gn = {
          id: je++,
          callback: it,
          priorityLevel: xe,
          startTime: bn,
          expirationTime: vr,
          sortIndex: -1
        };
        return bn > Gt ? (gn.sortIndex = bn, S(ge, gn), T(x) === null && gn === T(ge) && (ot ? la() : ot = !0, br(I, bn - Gt))) : (gn.sortIndex = vr, S(x, gn), !vt && !pt && (vt = !0, Qn(ye))), gn;
      }
      function Ye() {
      }
      function et() {
        !vt && !pt && (vt = !0, Qn(ye));
      }
      function ut() {
        return T(x);
      }
      function Ht(xe) {
        xe.callback = null;
      }
      function Te() {
        return Pe;
      }
      var Wt = !1, Fn = null, Ln = -1, Gn = y, _a = -1;
      function di() {
        var xe = u.unstable_now() - _a;
        return !(xe < Gn);
      }
      function Ir() {
      }
      function ir(xe) {
        if (xe < 0 || xe > 125) {
          console.error("forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported");
          return;
        }
        xe > 0 ? Gn = Math.floor(1e3 / xe) : Gn = y;
      }
      var dr = function() {
        if (Fn !== null) {
          var xe = u.unstable_now();
          _a = xe;
          var it = !0, Rt = !0;
          try {
            Rt = Fn(it, xe);
          } finally {
            Rt ? pr() : (Wt = !1, Fn = null);
          }
        } else
          Wt = !1;
      }, pr;
      if (typeof ke == "function")
        pr = function() {
          ke(dr);
        };
      else if (typeof MessageChannel < "u") {
        var Pr = new MessageChannel(), pi = Pr.port2;
        Pr.port1.onmessage = dr, pr = function() {
          pi.postMessage(null);
        };
      } else
        pr = function() {
          ie(dr, 0);
        };
      function Qn(xe) {
        Fn = xe, Wt || (Wt = !0, pr());
      }
      function br(xe, it) {
        Ln = ie(function() {
          xe(u.unstable_now());
        }, it);
      }
      function la() {
        Ie(Ln), Ln = -1;
      }
      var eo = Ir, ka = null;
      u.unstable_IdlePriority = B, u.unstable_ImmediatePriority = A, u.unstable_LowPriority = te, u.unstable_NormalPriority = U, u.unstable_Profiling = ka, u.unstable_UserBlockingPriority = F, u.unstable_cancelCallback = Ht, u.unstable_continueExecution = et, u.unstable_forceFrameRate = ir, u.unstable_getCurrentPriorityLevel = Te, u.unstable_getFirstCallbackNode = ut, u.unstable_next = Le, u.unstable_pauseExecution = Ye, u.unstable_requestPaint = eo, u.unstable_runWithPriority = be, u.unstable_scheduleCallback = we, u.unstable_shouldYield = di, u.unstable_wrapCallback = ze, typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u" && typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop == "function" && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop(new Error());
    }();
  }(BE)), BE;
}
var pR;
function tw() {
  if (pR) return Ky.exports;
  pR = 1;
  var u = {};
  return u.NODE_ENV === "production" ? Ky.exports = _N() : Ky.exports = kN(), Ky.exports;
}
/**
 * @license React
 * react-dom.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var vR;
function ON() {
  if (vR) return si;
  vR = 1;
  var u = Vt, f = tw();
  function v(n) {
    for (var r = "https://reactjs.org/docs/error-decoder.html?invariant=" + n, o = 1; o < arguments.length; o++) r += "&args[]=" + encodeURIComponent(arguments[o]);
    return "Minified React error #" + n + "; visit " + r + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
  }
  var y = /* @__PURE__ */ new Set(), S = {};
  function T(n, r) {
    _(n, r), _(n + "Capture", r);
  }
  function _(n, r) {
    for (S[n] = r, n = 0; n < r.length; n++) y.add(r[n]);
  }
  var g = !(typeof window > "u" || typeof window.document > "u" || typeof window.document.createElement > "u"), L = Object.prototype.hasOwnProperty, z = /^[:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD][:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\-.0-9\u00B7\u0300-\u036F\u203F-\u2040]*$/, A = {}, F = {};
  function U(n) {
    return L.call(F, n) ? !0 : L.call(A, n) ? !1 : z.test(n) ? F[n] = !0 : (A[n] = !0, !1);
  }
  function te(n, r, o, s) {
    if (o !== null && o.type === 0) return !1;
    switch (typeof r) {
      case "function":
      case "symbol":
        return !0;
      case "boolean":
        return s ? !1 : o !== null ? !o.acceptsBooleans : (n = n.toLowerCase().slice(0, 5), n !== "data-" && n !== "aria-");
      default:
        return !1;
    }
  }
  function B(n, r, o, s) {
    if (r === null || typeof r > "u" || te(n, r, o, s)) return !0;
    if (s) return !1;
    if (o !== null) switch (o.type) {
      case 3:
        return !r;
      case 4:
        return r === !1;
      case 5:
        return isNaN(r);
      case 6:
        return isNaN(r) || 1 > r;
    }
    return !1;
  }
  function M(n, r, o, s, d, h, b) {
    this.acceptsBooleans = r === 2 || r === 3 || r === 4, this.attributeName = s, this.attributeNamespace = d, this.mustUseProperty = o, this.propertyName = n, this.type = r, this.sanitizeURL = h, this.removeEmptyString = b;
  }
  var j = {};
  "children dangerouslySetInnerHTML defaultValue defaultChecked innerHTML suppressContentEditableWarning suppressHydrationWarning style".split(" ").forEach(function(n) {
    j[n] = new M(n, 0, !1, n, null, !1, !1);
  }), [["acceptCharset", "accept-charset"], ["className", "class"], ["htmlFor", "for"], ["httpEquiv", "http-equiv"]].forEach(function(n) {
    var r = n[0];
    j[r] = new M(r, 1, !1, n[1], null, !1, !1);
  }), ["contentEditable", "draggable", "spellCheck", "value"].forEach(function(n) {
    j[n] = new M(n, 2, !1, n.toLowerCase(), null, !1, !1);
  }), ["autoReverse", "externalResourcesRequired", "focusable", "preserveAlpha"].forEach(function(n) {
    j[n] = new M(n, 2, !1, n, null, !1, !1);
  }), "allowFullScreen async autoFocus autoPlay controls default defer disabled disablePictureInPicture disableRemotePlayback formNoValidate hidden loop noModule noValidate open playsInline readOnly required reversed scoped seamless itemScope".split(" ").forEach(function(n) {
    j[n] = new M(n, 3, !1, n.toLowerCase(), null, !1, !1);
  }), ["checked", "multiple", "muted", "selected"].forEach(function(n) {
    j[n] = new M(n, 3, !0, n, null, !1, !1);
  }), ["capture", "download"].forEach(function(n) {
    j[n] = new M(n, 4, !1, n, null, !1, !1);
  }), ["cols", "rows", "size", "span"].forEach(function(n) {
    j[n] = new M(n, 6, !1, n, null, !1, !1);
  }), ["rowSpan", "start"].forEach(function(n) {
    j[n] = new M(n, 5, !1, n.toLowerCase(), null, !1, !1);
  });
  var ce = /[\-:]([a-z])/g;
  function De(n) {
    return n[1].toUpperCase();
  }
  "accent-height alignment-baseline arabic-form baseline-shift cap-height clip-path clip-rule color-interpolation color-interpolation-filters color-profile color-rendering dominant-baseline enable-background fill-opacity fill-rule flood-color flood-opacity font-family font-size font-size-adjust font-stretch font-style font-variant font-weight glyph-name glyph-orientation-horizontal glyph-orientation-vertical horiz-adv-x horiz-origin-x image-rendering letter-spacing lighting-color marker-end marker-mid marker-start overline-position overline-thickness paint-order panose-1 pointer-events rendering-intent shape-rendering stop-color stop-opacity strikethrough-position strikethrough-thickness stroke-dasharray stroke-dashoffset stroke-linecap stroke-linejoin stroke-miterlimit stroke-opacity stroke-width text-anchor text-decoration text-rendering underline-position underline-thickness unicode-bidi unicode-range units-per-em v-alphabetic v-hanging v-ideographic v-mathematical vector-effect vert-adv-y vert-origin-x vert-origin-y word-spacing writing-mode xmlns:xlink x-height".split(" ").forEach(function(n) {
    var r = n.replace(
      ce,
      De
    );
    j[r] = new M(r, 1, !1, n, null, !1, !1);
  }), "xlink:actuate xlink:arcrole xlink:role xlink:show xlink:title xlink:type".split(" ").forEach(function(n) {
    var r = n.replace(ce, De);
    j[r] = new M(r, 1, !1, n, "http://www.w3.org/1999/xlink", !1, !1);
  }), ["xml:base", "xml:lang", "xml:space"].forEach(function(n) {
    var r = n.replace(ce, De);
    j[r] = new M(r, 1, !1, n, "http://www.w3.org/XML/1998/namespace", !1, !1);
  }), ["tabIndex", "crossOrigin"].forEach(function(n) {
    j[n] = new M(n, 1, !1, n.toLowerCase(), null, !1, !1);
  }), j.xlinkHref = new M("xlinkHref", 1, !1, "xlink:href", "http://www.w3.org/1999/xlink", !0, !1), ["src", "href", "action", "formAction"].forEach(function(n) {
    j[n] = new M(n, 1, !1, n.toLowerCase(), null, !0, !0);
  });
  function de(n, r, o, s) {
    var d = j.hasOwnProperty(r) ? j[r] : null;
    (d !== null ? d.type !== 0 : s || !(2 < r.length) || r[0] !== "o" && r[0] !== "O" || r[1] !== "n" && r[1] !== "N") && (B(r, o, d, s) && (o = null), s || d === null ? U(r) && (o === null ? n.removeAttribute(r) : n.setAttribute(r, "" + o)) : d.mustUseProperty ? n[d.propertyName] = o === null ? d.type === 3 ? !1 : "" : o : (r = d.attributeName, s = d.attributeNamespace, o === null ? n.removeAttribute(r) : (d = d.type, o = d === 3 || d === 4 && o === !0 ? "" : "" + o, s ? n.setAttributeNS(s, r, o) : n.setAttribute(r, o))));
  }
  var ue = u.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED, q = Symbol.for("react.element"), se = Symbol.for("react.portal"), Ce = Symbol.for("react.fragment"), Ge = Symbol.for("react.strict_mode"), _t = Symbol.for("react.profiler"), x = Symbol.for("react.provider"), ge = Symbol.for("react.context"), je = Symbol.for("react.forward_ref"), Qe = Symbol.for("react.suspense"), Pe = Symbol.for("react.suspense_list"), pt = Symbol.for("react.memo"), vt = Symbol.for("react.lazy"), ot = Symbol.for("react.offscreen"), ie = Symbol.iterator;
  function Ie(n) {
    return n === null || typeof n != "object" ? null : (n = ie && n[ie] || n["@@iterator"], typeof n == "function" ? n : null);
  }
  var ke = Object.assign, k;
  function I(n) {
    if (k === void 0) try {
      throw Error();
    } catch (o) {
      var r = o.stack.trim().match(/\n( *(at )?)/);
      k = r && r[1] || "";
    }
    return `
` + k + n;
  }
  var ye = !1;
  function Re(n, r) {
    if (!n || ye) return "";
    ye = !0;
    var o = Error.prepareStackTrace;
    Error.prepareStackTrace = void 0;
    try {
      if (r) if (r = function() {
        throw Error();
      }, Object.defineProperty(r.prototype, "props", { set: function() {
        throw Error();
      } }), typeof Reflect == "object" && Reflect.construct) {
        try {
          Reflect.construct(r, []);
        } catch (J) {
          var s = J;
        }
        Reflect.construct(n, [], r);
      } else {
        try {
          r.call();
        } catch (J) {
          s = J;
        }
        n.call(r.prototype);
      }
      else {
        try {
          throw Error();
        } catch (J) {
          s = J;
        }
        n();
      }
    } catch (J) {
      if (J && s && typeof J.stack == "string") {
        for (var d = J.stack.split(`
`), h = s.stack.split(`
`), b = d.length - 1, O = h.length - 1; 1 <= b && 0 <= O && d[b] !== h[O]; ) O--;
        for (; 1 <= b && 0 <= O; b--, O--) if (d[b] !== h[O]) {
          if (b !== 1 || O !== 1)
            do
              if (b--, O--, 0 > O || d[b] !== h[O]) {
                var P = `
` + d[b].replace(" at new ", " at ");
                return n.displayName && P.includes("<anonymous>") && (P = P.replace("<anonymous>", n.displayName)), P;
              }
            while (1 <= b && 0 <= O);
          break;
        }
      }
    } finally {
      ye = !1, Error.prepareStackTrace = o;
    }
    return (n = n ? n.displayName || n.name : "") ? I(n) : "";
  }
  function be(n) {
    switch (n.tag) {
      case 5:
        return I(n.type);
      case 16:
        return I("Lazy");
      case 13:
        return I("Suspense");
      case 19:
        return I("SuspenseList");
      case 0:
      case 2:
      case 15:
        return n = Re(n.type, !1), n;
      case 11:
        return n = Re(n.type.render, !1), n;
      case 1:
        return n = Re(n.type, !0), n;
      default:
        return "";
    }
  }
  function Le(n) {
    if (n == null) return null;
    if (typeof n == "function") return n.displayName || n.name || null;
    if (typeof n == "string") return n;
    switch (n) {
      case Ce:
        return "Fragment";
      case se:
        return "Portal";
      case _t:
        return "Profiler";
      case Ge:
        return "StrictMode";
      case Qe:
        return "Suspense";
      case Pe:
        return "SuspenseList";
    }
    if (typeof n == "object") switch (n.$$typeof) {
      case ge:
        return (n.displayName || "Context") + ".Consumer";
      case x:
        return (n._context.displayName || "Context") + ".Provider";
      case je:
        var r = n.render;
        return n = n.displayName, n || (n = r.displayName || r.name || "", n = n !== "" ? "ForwardRef(" + n + ")" : "ForwardRef"), n;
      case pt:
        return r = n.displayName || null, r !== null ? r : Le(n.type) || "Memo";
      case vt:
        r = n._payload, n = n._init;
        try {
          return Le(n(r));
        } catch {
        }
    }
    return null;
  }
  function ze(n) {
    var r = n.type;
    switch (n.tag) {
      case 24:
        return "Cache";
      case 9:
        return (r.displayName || "Context") + ".Consumer";
      case 10:
        return (r._context.displayName || "Context") + ".Provider";
      case 18:
        return "DehydratedFragment";
      case 11:
        return n = r.render, n = n.displayName || n.name || "", r.displayName || (n !== "" ? "ForwardRef(" + n + ")" : "ForwardRef");
      case 7:
        return "Fragment";
      case 5:
        return r;
      case 4:
        return "Portal";
      case 3:
        return "Root";
      case 6:
        return "Text";
      case 16:
        return Le(r);
      case 8:
        return r === Ge ? "StrictMode" : "Mode";
      case 22:
        return "Offscreen";
      case 12:
        return "Profiler";
      case 21:
        return "Scope";
      case 13:
        return "Suspense";
      case 19:
        return "SuspenseList";
      case 25:
        return "TracingMarker";
      case 1:
      case 0:
      case 17:
      case 2:
      case 14:
      case 15:
        if (typeof r == "function") return r.displayName || r.name || null;
        if (typeof r == "string") return r;
    }
    return null;
  }
  function we(n) {
    switch (typeof n) {
      case "boolean":
      case "number":
      case "string":
      case "undefined":
        return n;
      case "object":
        return n;
      default:
        return "";
    }
  }
  function Ye(n) {
    var r = n.type;
    return (n = n.nodeName) && n.toLowerCase() === "input" && (r === "checkbox" || r === "radio");
  }
  function et(n) {
    var r = Ye(n) ? "checked" : "value", o = Object.getOwnPropertyDescriptor(n.constructor.prototype, r), s = "" + n[r];
    if (!n.hasOwnProperty(r) && typeof o < "u" && typeof o.get == "function" && typeof o.set == "function") {
      var d = o.get, h = o.set;
      return Object.defineProperty(n, r, { configurable: !0, get: function() {
        return d.call(this);
      }, set: function(b) {
        s = "" + b, h.call(this, b);
      } }), Object.defineProperty(n, r, { enumerable: o.enumerable }), { getValue: function() {
        return s;
      }, setValue: function(b) {
        s = "" + b;
      }, stopTracking: function() {
        n._valueTracker = null, delete n[r];
      } };
    }
  }
  function ut(n) {
    n._valueTracker || (n._valueTracker = et(n));
  }
  function Ht(n) {
    if (!n) return !1;
    var r = n._valueTracker;
    if (!r) return !0;
    var o = r.getValue(), s = "";
    return n && (s = Ye(n) ? n.checked ? "true" : "false" : n.value), n = s, n !== o ? (r.setValue(n), !0) : !1;
  }
  function Te(n) {
    if (n = n || (typeof document < "u" ? document : void 0), typeof n > "u") return null;
    try {
      return n.activeElement || n.body;
    } catch {
      return n.body;
    }
  }
  function Wt(n, r) {
    var o = r.checked;
    return ke({}, r, { defaultChecked: void 0, defaultValue: void 0, value: void 0, checked: o ?? n._wrapperState.initialChecked });
  }
  function Fn(n, r) {
    var o = r.defaultValue == null ? "" : r.defaultValue, s = r.checked != null ? r.checked : r.defaultChecked;
    o = we(r.value != null ? r.value : o), n._wrapperState = { initialChecked: s, initialValue: o, controlled: r.type === "checkbox" || r.type === "radio" ? r.checked != null : r.value != null };
  }
  function Ln(n, r) {
    r = r.checked, r != null && de(n, "checked", r, !1);
  }
  function Gn(n, r) {
    Ln(n, r);
    var o = we(r.value), s = r.type;
    if (o != null) s === "number" ? (o === 0 && n.value === "" || n.value != o) && (n.value = "" + o) : n.value !== "" + o && (n.value = "" + o);
    else if (s === "submit" || s === "reset") {
      n.removeAttribute("value");
      return;
    }
    r.hasOwnProperty("value") ? di(n, r.type, o) : r.hasOwnProperty("defaultValue") && di(n, r.type, we(r.defaultValue)), r.checked == null && r.defaultChecked != null && (n.defaultChecked = !!r.defaultChecked);
  }
  function _a(n, r, o) {
    if (r.hasOwnProperty("value") || r.hasOwnProperty("defaultValue")) {
      var s = r.type;
      if (!(s !== "submit" && s !== "reset" || r.value !== void 0 && r.value !== null)) return;
      r = "" + n._wrapperState.initialValue, o || r === n.value || (n.value = r), n.defaultValue = r;
    }
    o = n.name, o !== "" && (n.name = ""), n.defaultChecked = !!n._wrapperState.initialChecked, o !== "" && (n.name = o);
  }
  function di(n, r, o) {
    (r !== "number" || Te(n.ownerDocument) !== n) && (o == null ? n.defaultValue = "" + n._wrapperState.initialValue : n.defaultValue !== "" + o && (n.defaultValue = "" + o));
  }
  var Ir = Array.isArray;
  function ir(n, r, o, s) {
    if (n = n.options, r) {
      r = {};
      for (var d = 0; d < o.length; d++) r["$" + o[d]] = !0;
      for (o = 0; o < n.length; o++) d = r.hasOwnProperty("$" + n[o].value), n[o].selected !== d && (n[o].selected = d), d && s && (n[o].defaultSelected = !0);
    } else {
      for (o = "" + we(o), r = null, d = 0; d < n.length; d++) {
        if (n[d].value === o) {
          n[d].selected = !0, s && (n[d].defaultSelected = !0);
          return;
        }
        r !== null || n[d].disabled || (r = n[d]);
      }
      r !== null && (r.selected = !0);
    }
  }
  function dr(n, r) {
    if (r.dangerouslySetInnerHTML != null) throw Error(v(91));
    return ke({}, r, { value: void 0, defaultValue: void 0, children: "" + n._wrapperState.initialValue });
  }
  function pr(n, r) {
    var o = r.value;
    if (o == null) {
      if (o = r.children, r = r.defaultValue, o != null) {
        if (r != null) throw Error(v(92));
        if (Ir(o)) {
          if (1 < o.length) throw Error(v(93));
          o = o[0];
        }
        r = o;
      }
      r == null && (r = ""), o = r;
    }
    n._wrapperState = { initialValue: we(o) };
  }
  function Pr(n, r) {
    var o = we(r.value), s = we(r.defaultValue);
    o != null && (o = "" + o, o !== n.value && (n.value = o), r.defaultValue == null && n.defaultValue !== o && (n.defaultValue = o)), s != null && (n.defaultValue = "" + s);
  }
  function pi(n) {
    var r = n.textContent;
    r === n._wrapperState.initialValue && r !== "" && r !== null && (n.value = r);
  }
  function Qn(n) {
    switch (n) {
      case "svg":
        return "http://www.w3.org/2000/svg";
      case "math":
        return "http://www.w3.org/1998/Math/MathML";
      default:
        return "http://www.w3.org/1999/xhtml";
    }
  }
  function br(n, r) {
    return n == null || n === "http://www.w3.org/1999/xhtml" ? Qn(r) : n === "http://www.w3.org/2000/svg" && r === "foreignObject" ? "http://www.w3.org/1999/xhtml" : n;
  }
  var la, eo = function(n) {
    return typeof MSApp < "u" && MSApp.execUnsafeLocalFunction ? function(r, o, s, d) {
      MSApp.execUnsafeLocalFunction(function() {
        return n(r, o, s, d);
      });
    } : n;
  }(function(n, r) {
    if (n.namespaceURI !== "http://www.w3.org/2000/svg" || "innerHTML" in n) n.innerHTML = r;
    else {
      for (la = la || document.createElement("div"), la.innerHTML = "<svg>" + r.valueOf().toString() + "</svg>", r = la.firstChild; n.firstChild; ) n.removeChild(n.firstChild);
      for (; r.firstChild; ) n.appendChild(r.firstChild);
    }
  });
  function ka(n, r) {
    if (r) {
      var o = n.firstChild;
      if (o && o === n.lastChild && o.nodeType === 3) {
        o.nodeValue = r;
        return;
      }
    }
    n.textContent = r;
  }
  var xe = {
    animationIterationCount: !0,
    aspectRatio: !0,
    borderImageOutset: !0,
    borderImageSlice: !0,
    borderImageWidth: !0,
    boxFlex: !0,
    boxFlexGroup: !0,
    boxOrdinalGroup: !0,
    columnCount: !0,
    columns: !0,
    flex: !0,
    flexGrow: !0,
    flexPositive: !0,
    flexShrink: !0,
    flexNegative: !0,
    flexOrder: !0,
    gridArea: !0,
    gridRow: !0,
    gridRowEnd: !0,
    gridRowSpan: !0,
    gridRowStart: !0,
    gridColumn: !0,
    gridColumnEnd: !0,
    gridColumnSpan: !0,
    gridColumnStart: !0,
    fontWeight: !0,
    lineClamp: !0,
    lineHeight: !0,
    opacity: !0,
    order: !0,
    orphans: !0,
    tabSize: !0,
    widows: !0,
    zIndex: !0,
    zoom: !0,
    fillOpacity: !0,
    floodOpacity: !0,
    stopOpacity: !0,
    strokeDasharray: !0,
    strokeDashoffset: !0,
    strokeMiterlimit: !0,
    strokeOpacity: !0,
    strokeWidth: !0
  }, it = ["Webkit", "ms", "Moz", "O"];
  Object.keys(xe).forEach(function(n) {
    it.forEach(function(r) {
      r = r + n.charAt(0).toUpperCase() + n.substring(1), xe[r] = xe[n];
    });
  });
  function Rt(n, r, o) {
    return r == null || typeof r == "boolean" || r === "" ? "" : o || typeof r != "number" || r === 0 || xe.hasOwnProperty(n) && xe[n] ? ("" + r).trim() : r + "px";
  }
  function Gt(n, r) {
    n = n.style;
    for (var o in r) if (r.hasOwnProperty(o)) {
      var s = o.indexOf("--") === 0, d = Rt(o, r[o], s);
      o === "float" && (o = "cssFloat"), s ? n.setProperty(o, d) : n[o] = d;
    }
  }
  var bn = ke({ menuitem: !0 }, { area: !0, base: !0, br: !0, col: !0, embed: !0, hr: !0, img: !0, input: !0, keygen: !0, link: !0, meta: !0, param: !0, source: !0, track: !0, wbr: !0 });
  function Tn(n, r) {
    if (r) {
      if (bn[n] && (r.children != null || r.dangerouslySetInnerHTML != null)) throw Error(v(137, n));
      if (r.dangerouslySetInnerHTML != null) {
        if (r.children != null) throw Error(v(60));
        if (typeof r.dangerouslySetInnerHTML != "object" || !("__html" in r.dangerouslySetInnerHTML)) throw Error(v(61));
      }
      if (r.style != null && typeof r.style != "object") throw Error(v(62));
    }
  }
  function Rn(n, r) {
    if (n.indexOf("-") === -1) return typeof r.is == "string";
    switch (n) {
      case "annotation-xml":
      case "color-profile":
      case "font-face":
      case "font-face-src":
      case "font-face-uri":
      case "font-face-format":
      case "font-face-name":
      case "missing-glyph":
        return !1;
      default:
        return !0;
    }
  }
  var vr = null;
  function gn(n) {
    return n = n.target || n.srcElement || window, n.correspondingUseElement && (n = n.correspondingUseElement), n.nodeType === 3 ? n.parentNode : n;
  }
  var an = null, Qt = null, Oa = null;
  function Ia(n) {
    if (n = Vs(n)) {
      if (typeof an != "function") throw Error(v(280));
      var r = n.stateNode;
      r && (r = ho(r), an(n.stateNode, n.type, r));
    }
  }
  function Ya(n) {
    Qt ? Oa ? Oa.push(n) : Oa = [n] : Qt = n;
  }
  function to() {
    if (Qt) {
      var n = Qt, r = Oa;
      if (Oa = Qt = null, Ia(n), r) for (n = 0; n < r.length; n++) Ia(r[n]);
    }
  }
  function Sl(n, r) {
    return n(r);
  }
  function El() {
  }
  var no = !1;
  function Cl(n, r, o) {
    if (no) return n(r, o);
    no = !0;
    try {
      return Sl(n, r, o);
    } finally {
      no = !1, (Qt !== null || Oa !== null) && (El(), to());
    }
  }
  function Di(n, r) {
    var o = n.stateNode;
    if (o === null) return null;
    var s = ho(o);
    if (s === null) return null;
    o = s[r];
    e: switch (r) {
      case "onClick":
      case "onClickCapture":
      case "onDoubleClick":
      case "onDoubleClickCapture":
      case "onMouseDown":
      case "onMouseDownCapture":
      case "onMouseMove":
      case "onMouseMoveCapture":
      case "onMouseUp":
      case "onMouseUpCapture":
      case "onMouseEnter":
        (s = !s.disabled) || (n = n.type, s = !(n === "button" || n === "input" || n === "select" || n === "textarea")), n = !s;
        break e;
      default:
        n = !1;
    }
    if (n) return null;
    if (o && typeof o != "function") throw Error(v(231, r, typeof o));
    return o;
  }
  var Da = !1;
  if (g) try {
    var Tr = {};
    Object.defineProperty(Tr, "passive", { get: function() {
      Da = !0;
    } }), window.addEventListener("test", Tr, Tr), window.removeEventListener("test", Tr, Tr);
  } catch {
    Da = !1;
  }
  function Na(n, r, o, s, d, h, b, O, P) {
    var J = Array.prototype.slice.call(arguments, 3);
    try {
      r.apply(o, J);
    } catch (ve) {
      this.onError(ve);
    }
  }
  var ua = !1, Ni = null, Ai = !1, ro = null, N = { onError: function(n) {
    ua = !0, Ni = n;
  } };
  function fe(n, r, o, s, d, h, b, O, P) {
    ua = !1, Ni = null, Na.apply(N, arguments);
  }
  function Ae(n, r, o, s, d, h, b, O, P) {
    if (fe.apply(this, arguments), ua) {
      if (ua) {
        var J = Ni;
        ua = !1, Ni = null;
      } else throw Error(v(198));
      Ai || (Ai = !0, ro = J);
    }
  }
  function Ue(n) {
    var r = n, o = n;
    if (n.alternate) for (; r.return; ) r = r.return;
    else {
      n = r;
      do
        r = n, r.flags & 4098 && (o = r.return), n = r.return;
      while (n);
    }
    return r.tag === 3 ? o : null;
  }
  function kt(n) {
    if (n.tag === 13) {
      var r = n.memoizedState;
      if (r === null && (n = n.alternate, n !== null && (r = n.memoizedState)), r !== null) return r.dehydrated;
    }
    return null;
  }
  function yt(n) {
    if (Ue(n) !== n) throw Error(v(188));
  }
  function Nt(n) {
    var r = n.alternate;
    if (!r) {
      if (r = Ue(n), r === null) throw Error(v(188));
      return r !== n ? null : n;
    }
    for (var o = n, s = r; ; ) {
      var d = o.return;
      if (d === null) break;
      var h = d.alternate;
      if (h === null) {
        if (s = d.return, s !== null) {
          o = s;
          continue;
        }
        break;
      }
      if (d.child === h.child) {
        for (h = d.child; h; ) {
          if (h === o) return yt(d), n;
          if (h === s) return yt(d), r;
          h = h.sibling;
        }
        throw Error(v(188));
      }
      if (o.return !== s.return) o = d, s = h;
      else {
        for (var b = !1, O = d.child; O; ) {
          if (O === o) {
            b = !0, o = d, s = h;
            break;
          }
          if (O === s) {
            b = !0, s = d, o = h;
            break;
          }
          O = O.sibling;
        }
        if (!b) {
          for (O = h.child; O; ) {
            if (O === o) {
              b = !0, o = h, s = d;
              break;
            }
            if (O === s) {
              b = !0, s = h, o = d;
              break;
            }
            O = O.sibling;
          }
          if (!b) throw Error(v(189));
        }
      }
      if (o.alternate !== s) throw Error(v(190));
    }
    if (o.tag !== 3) throw Error(v(188));
    return o.stateNode.current === o ? n : r;
  }
  function wt(n) {
    return n = Nt(n), n !== null ? jn(n) : null;
  }
  function jn(n) {
    if (n.tag === 5 || n.tag === 6) return n;
    for (n = n.child; n !== null; ) {
      var r = jn(n);
      if (r !== null) return r;
      n = n.sibling;
    }
    return null;
  }
  var Sn = f.unstable_scheduleCallback, wn = f.unstable_cancelCallback, $r = f.unstable_shouldYield, vi = f.unstable_requestPaint, qt = f.unstable_now, Dn = f.unstable_getCurrentPriorityLevel, Et = f.unstable_ImmediatePriority, Mi = f.unstable_UserBlockingPriority, ao = f.unstable_NormalPriority, jc = f.unstable_LowPriority, io = f.unstable_IdlePriority, No = null, sa = null;
  function Cs(n) {
    if (sa && typeof sa.onCommitFiberRoot == "function") try {
      sa.onCommitFiberRoot(No, n, void 0, (n.current.flags & 128) === 128);
    } catch {
    }
  }
  var Yr = Math.clz32 ? Math.clz32 : Vc, bs = Math.log, Hc = Math.LN2;
  function Vc(n) {
    return n >>>= 0, n === 0 ? 32 : 31 - (bs(n) / Hc | 0) | 0;
  }
  var oo = 64, Ao = 4194304;
  function ca(n) {
    switch (n & -n) {
      case 1:
        return 1;
      case 2:
        return 2;
      case 4:
        return 4;
      case 8:
        return 8;
      case 16:
        return 16;
      case 32:
        return 32;
      case 64:
      case 128:
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
        return n & 4194240;
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
      case 67108864:
        return n & 130023424;
      case 134217728:
        return 134217728;
      case 268435456:
        return 268435456;
      case 536870912:
        return 536870912;
      case 1073741824:
        return 1073741824;
      default:
        return n;
    }
  }
  function Li(n, r) {
    var o = n.pendingLanes;
    if (o === 0) return 0;
    var s = 0, d = n.suspendedLanes, h = n.pingedLanes, b = o & 268435455;
    if (b !== 0) {
      var O = b & ~d;
      O !== 0 ? s = ca(O) : (h &= b, h !== 0 && (s = ca(h)));
    } else b = o & ~d, b !== 0 ? s = ca(b) : h !== 0 && (s = ca(h));
    if (s === 0) return 0;
    if (r !== 0 && r !== s && !(r & d) && (d = s & -s, h = r & -r, d >= h || d === 16 && (h & 4194240) !== 0)) return r;
    if (s & 4 && (s |= o & 16), r = n.entangledLanes, r !== 0) for (n = n.entanglements, r &= s; 0 < r; ) o = 31 - Yr(r), d = 1 << o, s |= n[o], r &= ~d;
    return s;
  }
  function Mo(n, r) {
    switch (n) {
      case 1:
      case 2:
      case 4:
        return r + 250;
      case 8:
      case 16:
      case 32:
      case 64:
      case 128:
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
        return r + 5e3;
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
      case 67108864:
        return -1;
      case 134217728:
      case 268435456:
      case 536870912:
      case 1073741824:
        return -1;
      default:
        return -1;
    }
  }
  function hu(n, r) {
    for (var o = n.suspendedLanes, s = n.pingedLanes, d = n.expirationTimes, h = n.pendingLanes; 0 < h; ) {
      var b = 31 - Yr(h), O = 1 << b, P = d[b];
      P === -1 ? (!(O & o) || O & s) && (d[b] = Mo(O, r)) : P <= r && (n.expiredLanes |= O), h &= ~O;
    }
  }
  function lo(n) {
    return n = n.pendingLanes & -1073741825, n !== 0 ? n : n & 1073741824 ? 1073741824 : 0;
  }
  function bl() {
    var n = oo;
    return oo <<= 1, !(oo & 4194240) && (oo = 64), n;
  }
  function Tl(n) {
    for (var r = [], o = 0; 31 > o; o++) r.push(n);
    return r;
  }
  function Lo(n, r, o) {
    n.pendingLanes |= r, r !== 536870912 && (n.suspendedLanes = 0, n.pingedLanes = 0), n = n.eventTimes, r = 31 - Yr(r), n[r] = o;
  }
  function Ts(n, r) {
    var o = n.pendingLanes & ~r;
    n.pendingLanes = r, n.suspendedLanes = 0, n.pingedLanes = 0, n.expiredLanes &= r, n.mutableReadLanes &= r, n.entangledLanes &= r, r = n.entanglements;
    var s = n.eventTimes;
    for (n = n.expirationTimes; 0 < o; ) {
      var d = 31 - Yr(o), h = 1 << d;
      r[d] = 0, s[d] = -1, n[d] = -1, o &= ~h;
    }
  }
  function Rs(n, r) {
    var o = n.entangledLanes |= r;
    for (n = n.entanglements; o; ) {
      var s = 31 - Yr(o), d = 1 << s;
      d & r | n[s] & r && (n[s] |= r), o &= ~d;
    }
  }
  var Pt = 0;
  function ws(n) {
    return n &= -n, 1 < n ? 4 < n ? n & 268435455 ? 16 : 536870912 : 4 : 1;
  }
  var mu, $t, Bc, zi, ht, Rl = !1, hr = [], fa = null, Wr = null, Ui = null, zn = /* @__PURE__ */ new Map(), on = /* @__PURE__ */ new Map(), hi = [], Wa = "mousedown mouseup touchcancel touchend touchstart auxclick dblclick pointercancel pointerdown pointerup dragend dragstart drop compositionend compositionstart keydown keypress keyup input textInput copy cut paste click change contextmenu reset submit".split(" ");
  function Fr(n, r) {
    switch (n) {
      case "focusin":
      case "focusout":
        fa = null;
        break;
      case "dragenter":
      case "dragleave":
        Wr = null;
        break;
      case "mouseover":
      case "mouseout":
        Ui = null;
        break;
      case "pointerover":
      case "pointerout":
        zn.delete(r.pointerId);
        break;
      case "gotpointercapture":
      case "lostpointercapture":
        on.delete(r.pointerId);
    }
  }
  function Gr(n, r, o, s, d, h) {
    return n === null || n.nativeEvent !== h ? (n = { blockedOn: r, domEventName: o, eventSystemFlags: s, nativeEvent: h, targetContainers: [d] }, r !== null && (r = Vs(r), r !== null && $t(r)), n) : (n.eventSystemFlags |= s, r = n.targetContainers, d !== null && r.indexOf(d) === -1 && r.push(d), n);
  }
  function Vd(n, r, o, s, d) {
    switch (r) {
      case "focusin":
        return fa = Gr(fa, n, r, o, s, d), !0;
      case "dragenter":
        return Wr = Gr(Wr, n, r, o, s, d), !0;
      case "mouseover":
        return Ui = Gr(Ui, n, r, o, s, d), !0;
      case "pointerover":
        var h = d.pointerId;
        return zn.set(h, Gr(zn.get(h) || null, n, r, o, s, d)), !0;
      case "gotpointercapture":
        return h = d.pointerId, on.set(h, Gr(on.get(h) || null, n, r, o, s, d)), !0;
    }
    return !1;
  }
  function yu(n) {
    var r = Ml(n.target);
    if (r !== null) {
      var o = Ue(r);
      if (o !== null) {
        if (r = o.tag, r === 13) {
          if (r = kt(o), r !== null) {
            n.blockedOn = r, ht(n.priority, function() {
              Bc(o);
            });
            return;
          }
        } else if (r === 3 && o.stateNode.current.memoizedState.isDehydrated) {
          n.blockedOn = o.tag === 3 ? o.stateNode.containerInfo : null;
          return;
        }
      }
    }
    n.blockedOn = null;
  }
  function wl(n) {
    if (n.blockedOn !== null) return !1;
    for (var r = n.targetContainers; 0 < r.length; ) {
      var o = Cu(n.domEventName, n.eventSystemFlags, r[0], n.nativeEvent);
      if (o === null) {
        o = n.nativeEvent;
        var s = new o.constructor(o.type, o);
        vr = s, o.target.dispatchEvent(s), vr = null;
      } else return r = Vs(o), r !== null && $t(r), n.blockedOn = o, !1;
      r.shift();
    }
    return !0;
  }
  function gu(n, r, o) {
    wl(n) && o.delete(r);
  }
  function Su() {
    Rl = !1, fa !== null && wl(fa) && (fa = null), Wr !== null && wl(Wr) && (Wr = null), Ui !== null && wl(Ui) && (Ui = null), zn.forEach(gu), on.forEach(gu);
  }
  function xl(n, r) {
    n.blockedOn === r && (n.blockedOn = null, Rl || (Rl = !0, f.unstable_scheduleCallback(f.unstable_NormalPriority, Su)));
  }
  function Ga(n) {
    function r(d) {
      return xl(d, n);
    }
    if (0 < hr.length) {
      xl(hr[0], n);
      for (var o = 1; o < hr.length; o++) {
        var s = hr[o];
        s.blockedOn === n && (s.blockedOn = null);
      }
    }
    for (fa !== null && xl(fa, n), Wr !== null && xl(Wr, n), Ui !== null && xl(Ui, n), zn.forEach(r), on.forEach(r), o = 0; o < hi.length; o++) s = hi[o], s.blockedOn === n && (s.blockedOn = null);
    for (; 0 < hi.length && (o = hi[0], o.blockedOn === null); ) yu(o), o.blockedOn === null && hi.shift();
  }
  var Qa = ue.ReactCurrentBatchConfig, zo = !0;
  function uo(n, r, o, s) {
    var d = Pt, h = Qa.transition;
    Qa.transition = null;
    try {
      Pt = 1, Uo(n, r, o, s);
    } finally {
      Pt = d, Qa.transition = h;
    }
  }
  function Eu(n, r, o, s) {
    var d = Pt, h = Qa.transition;
    Qa.transition = null;
    try {
      Pt = 4, Uo(n, r, o, s);
    } finally {
      Pt = d, Qa.transition = h;
    }
  }
  function Uo(n, r, o, s) {
    if (zo) {
      var d = Cu(n, r, o, s);
      if (d === null) tp(n, r, s, so, o), Fr(n, s);
      else if (Vd(d, n, r, o, s)) s.stopPropagation();
      else if (Fr(n, s), r & 4 && -1 < Wa.indexOf(n)) {
        for (; d !== null; ) {
          var h = Vs(d);
          if (h !== null && mu(h), h = Cu(n, r, o, s), h === null && tp(n, r, s, so, o), h === d) break;
          d = h;
        }
        d !== null && s.stopPropagation();
      } else tp(n, r, s, null, o);
    }
  }
  var so = null;
  function Cu(n, r, o, s) {
    if (so = null, n = gn(s), n = Ml(n), n !== null) if (r = Ue(n), r === null) n = null;
    else if (o = r.tag, o === 13) {
      if (n = kt(r), n !== null) return n;
      n = null;
    } else if (o === 3) {
      if (r.stateNode.current.memoizedState.isDehydrated) return r.tag === 3 ? r.stateNode.containerInfo : null;
      n = null;
    } else r !== n && (n = null);
    return so = n, null;
  }
  function xs(n) {
    switch (n) {
      case "cancel":
      case "click":
      case "close":
      case "contextmenu":
      case "copy":
      case "cut":
      case "auxclick":
      case "dblclick":
      case "dragend":
      case "dragstart":
      case "drop":
      case "focusin":
      case "focusout":
      case "input":
      case "invalid":
      case "keydown":
      case "keypress":
      case "keyup":
      case "mousedown":
      case "mouseup":
      case "paste":
      case "pause":
      case "play":
      case "pointercancel":
      case "pointerdown":
      case "pointerup":
      case "ratechange":
      case "reset":
      case "resize":
      case "seeked":
      case "submit":
      case "touchcancel":
      case "touchend":
      case "touchstart":
      case "volumechange":
      case "change":
      case "selectionchange":
      case "textInput":
      case "compositionstart":
      case "compositionend":
      case "compositionupdate":
      case "beforeblur":
      case "afterblur":
      case "beforeinput":
      case "blur":
      case "fullscreenchange":
      case "focus":
      case "hashchange":
      case "popstate":
      case "select":
      case "selectstart":
        return 1;
      case "drag":
      case "dragenter":
      case "dragexit":
      case "dragleave":
      case "dragover":
      case "mousemove":
      case "mouseout":
      case "mouseover":
      case "pointermove":
      case "pointerout":
      case "pointerover":
      case "scroll":
      case "toggle":
      case "touchmove":
      case "wheel":
      case "mouseenter":
      case "mouseleave":
      case "pointerenter":
      case "pointerleave":
        return 4;
      case "message":
        switch (Dn()) {
          case Et:
            return 1;
          case Mi:
            return 4;
          case ao:
          case jc:
            return 16;
          case io:
            return 536870912;
          default:
            return 16;
        }
      default:
        return 16;
    }
  }
  var qa = null, bu = null, C = null;
  function D() {
    if (C) return C;
    var n, r = bu, o = r.length, s, d = "value" in qa ? qa.value : qa.textContent, h = d.length;
    for (n = 0; n < o && r[n] === d[n]; n++) ;
    var b = o - n;
    for (s = 1; s <= b && r[o - s] === d[h - s]; s++) ;
    return C = d.slice(n, 1 < s ? 1 - s : void 0);
  }
  function K(n) {
    var r = n.keyCode;
    return "charCode" in n ? (n = n.charCode, n === 0 && r === 13 && (n = 13)) : n = r, n === 10 && (n = 13), 32 <= n || n === 13 ? n : 0;
  }
  function ee() {
    return !0;
  }
  function Ee() {
    return !1;
  }
  function Ke(n) {
    function r(o, s, d, h, b) {
      this._reactName = o, this._targetInst = d, this.type = s, this.nativeEvent = h, this.target = b, this.currentTarget = null;
      for (var O in n) n.hasOwnProperty(O) && (o = n[O], this[O] = o ? o(h) : h[O]);
      return this.isDefaultPrevented = (h.defaultPrevented != null ? h.defaultPrevented : h.returnValue === !1) ? ee : Ee, this.isPropagationStopped = Ee, this;
    }
    return ke(r.prototype, { preventDefault: function() {
      this.defaultPrevented = !0;
      var o = this.nativeEvent;
      o && (o.preventDefault ? o.preventDefault() : typeof o.returnValue != "unknown" && (o.returnValue = !1), this.isDefaultPrevented = ee);
    }, stopPropagation: function() {
      var o = this.nativeEvent;
      o && (o.stopPropagation ? o.stopPropagation() : typeof o.cancelBubble != "unknown" && (o.cancelBubble = !0), this.isPropagationStopped = ee);
    }, persist: function() {
    }, isPersistent: ee }), r;
  }
  var He = { eventPhase: 0, bubbles: 0, cancelable: 0, timeStamp: function(n) {
    return n.timeStamp || Date.now();
  }, defaultPrevented: 0, isTrusted: 0 }, ft = Ke(He), xt = ke({}, He, { view: 0, detail: 0 }), Kt = Ke(xt), ln, un, bt, hn = ke({}, xt, { screenX: 0, screenY: 0, clientX: 0, clientY: 0, pageX: 0, pageY: 0, ctrlKey: 0, shiftKey: 0, altKey: 0, metaKey: 0, getModifierState: mi, button: 0, buttons: 0, relatedTarget: function(n) {
    return n.relatedTarget === void 0 ? n.fromElement === n.srcElement ? n.toElement : n.fromElement : n.relatedTarget;
  }, movementX: function(n) {
    return "movementX" in n ? n.movementX : (n !== bt && (bt && n.type === "mousemove" ? (ln = n.screenX - bt.screenX, un = n.screenY - bt.screenY) : un = ln = 0, bt = n), ln);
  }, movementY: function(n) {
    return "movementY" in n ? n.movementY : un;
  } }), Hn = Ke(hn), _l = ke({}, hn, { dataTransfer: 0 }), _s = Ke(_l), co = ke({}, xt, { relatedTarget: 0 }), kl = Ke(co), ks = ke({}, He, { animationName: 0, elapsedTime: 0, pseudoElement: 0 }), Bd = Ke(ks), Ic = ke({}, He, { clipboardData: function(n) {
    return "clipboardData" in n ? n.clipboardData : window.clipboardData;
  } }), Id = Ke(Ic), ih = ke({}, He, { data: 0 }), Yc = Ke(ih), oh = {
    Esc: "Escape",
    Spacebar: " ",
    Left: "ArrowLeft",
    Up: "ArrowUp",
    Right: "ArrowRight",
    Down: "ArrowDown",
    Del: "Delete",
    Win: "OS",
    Menu: "ContextMenu",
    Apps: "ContextMenu",
    Scroll: "ScrollLock",
    MozPrintableKey: "Unidentified"
  }, lh = {
    8: "Backspace",
    9: "Tab",
    12: "Clear",
    13: "Enter",
    16: "Shift",
    17: "Control",
    18: "Alt",
    19: "Pause",
    20: "CapsLock",
    27: "Escape",
    32: " ",
    33: "PageUp",
    34: "PageDown",
    35: "End",
    36: "Home",
    37: "ArrowLeft",
    38: "ArrowUp",
    39: "ArrowRight",
    40: "ArrowDown",
    45: "Insert",
    46: "Delete",
    112: "F1",
    113: "F2",
    114: "F3",
    115: "F4",
    116: "F5",
    117: "F6",
    118: "F7",
    119: "F8",
    120: "F9",
    121: "F10",
    122: "F11",
    123: "F12",
    144: "NumLock",
    145: "ScrollLock",
    224: "Meta"
  }, uh = { Alt: "altKey", Control: "ctrlKey", Meta: "metaKey", Shift: "shiftKey" };
  function wg(n) {
    var r = this.nativeEvent;
    return r.getModifierState ? r.getModifierState(n) : (n = uh[n]) ? !!r[n] : !1;
  }
  function mi() {
    return wg;
  }
  var xg = ke({}, xt, { key: function(n) {
    if (n.key) {
      var r = oh[n.key] || n.key;
      if (r !== "Unidentified") return r;
    }
    return n.type === "keypress" ? (n = K(n), n === 13 ? "Enter" : String.fromCharCode(n)) : n.type === "keydown" || n.type === "keyup" ? lh[n.keyCode] || "Unidentified" : "";
  }, code: 0, location: 0, ctrlKey: 0, shiftKey: 0, altKey: 0, metaKey: 0, repeat: 0, locale: 0, getModifierState: mi, charCode: function(n) {
    return n.type === "keypress" ? K(n) : 0;
  }, keyCode: function(n) {
    return n.type === "keydown" || n.type === "keyup" ? n.keyCode : 0;
  }, which: function(n) {
    return n.type === "keypress" ? K(n) : n.type === "keydown" || n.type === "keyup" ? n.keyCode : 0;
  } }), Yd = Ke(xg), Wd = ke({}, hn, { pointerId: 0, width: 0, height: 0, pressure: 0, tangentialPressure: 0, tiltX: 0, tiltY: 0, twist: 0, pointerType: 0, isPrimary: 0 }), Wc = Ke(Wd), _g = ke({}, xt, { touches: 0, targetTouches: 0, changedTouches: 0, altKey: 0, metaKey: 0, ctrlKey: 0, shiftKey: 0, getModifierState: mi }), Gc = Ke(_g), sh = ke({}, He, { propertyName: 0, elapsedTime: 0, pseudoElement: 0 }), da = Ke(sh), fo = ke({}, hn, {
    deltaX: function(n) {
      return "deltaX" in n ? n.deltaX : "wheelDeltaX" in n ? -n.wheelDeltaX : 0;
    },
    deltaY: function(n) {
      return "deltaY" in n ? n.deltaY : "wheelDeltaY" in n ? -n.wheelDeltaY : "wheelDelta" in n ? -n.wheelDelta : 0;
    },
    deltaZ: 0,
    deltaMode: 0
  }), qn = Ke(fo), po = [9, 13, 27, 32], Os = g && "CompositionEvent" in window, Po = null;
  g && "documentMode" in document && (Po = document.documentMode);
  var kg = g && "TextEvent" in window && !Po, Tu = g && (!Os || Po && 8 < Po && 11 >= Po), ch = " ", fh = !1;
  function Qc(n, r) {
    switch (n) {
      case "keyup":
        return po.indexOf(r.keyCode) !== -1;
      case "keydown":
        return r.keyCode !== 229;
      case "keypress":
      case "mousedown":
      case "focusout":
        return !0;
      default:
        return !1;
    }
  }
  function dh(n) {
    return n = n.detail, typeof n == "object" && "data" in n ? n.data : null;
  }
  var Ru = !1;
  function Og(n, r) {
    switch (n) {
      case "compositionend":
        return dh(r);
      case "keypress":
        return r.which !== 32 ? null : (fh = !0, ch);
      case "textInput":
        return n = r.data, n === ch && fh ? null : n;
      default:
        return null;
    }
  }
  function ph(n, r) {
    if (Ru) return n === "compositionend" || !Os && Qc(n, r) ? (n = D(), C = bu = qa = null, Ru = !1, n) : null;
    switch (n) {
      case "paste":
        return null;
      case "keypress":
        if (!(r.ctrlKey || r.altKey || r.metaKey) || r.ctrlKey && r.altKey) {
          if (r.char && 1 < r.char.length) return r.char;
          if (r.which) return String.fromCharCode(r.which);
        }
        return null;
      case "compositionend":
        return Tu && r.locale !== "ko" ? null : r.data;
      default:
        return null;
    }
  }
  var Dg = { color: !0, date: !0, datetime: !0, "datetime-local": !0, email: !0, month: !0, number: !0, password: !0, range: !0, search: !0, tel: !0, text: !0, time: !0, url: !0, week: !0 };
  function vh(n) {
    var r = n && n.nodeName && n.nodeName.toLowerCase();
    return r === "input" ? !!Dg[n.type] : r === "textarea";
  }
  function hh(n, r, o, s) {
    Ya(s), r = Fs(r, "onChange"), 0 < r.length && (o = new ft("onChange", "change", null, o, s), n.push({ event: o, listeners: r }));
  }
  var wu = null, Pi = null;
  function Gd(n) {
    Jc(n, 0);
  }
  function Ds(n) {
    var r = nt(n);
    if (Ht(r)) return n;
  }
  function mh(n, r) {
    if (n === "change") return r;
  }
  var yh = !1;
  if (g) {
    var Qd;
    if (g) {
      var qd = "oninput" in document;
      if (!qd) {
        var gh = document.createElement("div");
        gh.setAttribute("oninput", "return;"), qd = typeof gh.oninput == "function";
      }
      Qd = qd;
    } else Qd = !1;
    yh = Qd && (!document.documentMode || 9 < document.documentMode);
  }
  function Sh() {
    wu && (wu.detachEvent("onpropertychange", Eh), Pi = wu = null);
  }
  function Eh(n) {
    if (n.propertyName === "value" && Ds(Pi)) {
      var r = [];
      hh(r, Pi, n, gn(n)), Cl(Gd, r);
    }
  }
  function Ng(n, r, o) {
    n === "focusin" ? (Sh(), wu = r, Pi = o, wu.attachEvent("onpropertychange", Eh)) : n === "focusout" && Sh();
  }
  function Ag(n) {
    if (n === "selectionchange" || n === "keyup" || n === "keydown") return Ds(Pi);
  }
  function Ch(n, r) {
    if (n === "click") return Ds(r);
  }
  function Mg(n, r) {
    if (n === "input" || n === "change") return Ds(r);
  }
  function bh(n, r) {
    return n === r && (n !== 0 || 1 / n === 1 / r) || n !== n && r !== r;
  }
  var yi = typeof Object.is == "function" ? Object.is : bh;
  function Ns(n, r) {
    if (yi(n, r)) return !0;
    if (typeof n != "object" || n === null || typeof r != "object" || r === null) return !1;
    var o = Object.keys(n), s = Object.keys(r);
    if (o.length !== s.length) return !1;
    for (s = 0; s < o.length; s++) {
      var d = o[s];
      if (!L.call(r, d) || !yi(n[d], r[d])) return !1;
    }
    return !0;
  }
  function Th(n) {
    for (; n && n.firstChild; ) n = n.firstChild;
    return n;
  }
  function Rh(n, r) {
    var o = Th(n);
    n = 0;
    for (var s; o; ) {
      if (o.nodeType === 3) {
        if (s = n + o.textContent.length, n <= r && s >= r) return { node: o, offset: r - n };
        n = s;
      }
      e: {
        for (; o; ) {
          if (o.nextSibling) {
            o = o.nextSibling;
            break e;
          }
          o = o.parentNode;
        }
        o = void 0;
      }
      o = Th(o);
    }
  }
  function qc(n, r) {
    return n && r ? n === r ? !0 : n && n.nodeType === 3 ? !1 : r && r.nodeType === 3 ? qc(n, r.parentNode) : "contains" in n ? n.contains(r) : n.compareDocumentPosition ? !!(n.compareDocumentPosition(r) & 16) : !1 : !1;
  }
  function $o() {
    for (var n = window, r = Te(); r instanceof n.HTMLIFrameElement; ) {
      try {
        var o = typeof r.contentWindow.location.href == "string";
      } catch {
        o = !1;
      }
      if (o) n = r.contentWindow;
      else break;
      r = Te(n.document);
    }
    return r;
  }
  function xu(n) {
    var r = n && n.nodeName && n.nodeName.toLowerCase();
    return r && (r === "input" && (n.type === "text" || n.type === "search" || n.type === "tel" || n.type === "url" || n.type === "password") || r === "textarea" || n.contentEditable === "true");
  }
  function wh(n) {
    var r = $o(), o = n.focusedElem, s = n.selectionRange;
    if (r !== o && o && o.ownerDocument && qc(o.ownerDocument.documentElement, o)) {
      if (s !== null && xu(o)) {
        if (r = s.start, n = s.end, n === void 0 && (n = r), "selectionStart" in o) o.selectionStart = r, o.selectionEnd = Math.min(n, o.value.length);
        else if (n = (r = o.ownerDocument || document) && r.defaultView || window, n.getSelection) {
          n = n.getSelection();
          var d = o.textContent.length, h = Math.min(s.start, d);
          s = s.end === void 0 ? h : Math.min(s.end, d), !n.extend && h > s && (d = s, s = h, h = d), d = Rh(o, h);
          var b = Rh(
            o,
            s
          );
          d && b && (n.rangeCount !== 1 || n.anchorNode !== d.node || n.anchorOffset !== d.offset || n.focusNode !== b.node || n.focusOffset !== b.offset) && (r = r.createRange(), r.setStart(d.node, d.offset), n.removeAllRanges(), h > s ? (n.addRange(r), n.extend(b.node, b.offset)) : (r.setEnd(b.node, b.offset), n.addRange(r)));
        }
      }
      for (r = [], n = o; n = n.parentNode; ) n.nodeType === 1 && r.push({ element: n, left: n.scrollLeft, top: n.scrollTop });
      for (typeof o.focus == "function" && o.focus(), o = 0; o < r.length; o++) n = r[o], n.element.scrollLeft = n.left, n.element.scrollTop = n.top;
    }
  }
  var _u = g && "documentMode" in document && 11 >= document.documentMode, ku = null, Kd = null, As = null, Xd = !1;
  function xh(n, r, o) {
    var s = o.window === o ? o.document : o.nodeType === 9 ? o : o.ownerDocument;
    Xd || ku == null || ku !== Te(s) || (s = ku, "selectionStart" in s && xu(s) ? s = { start: s.selectionStart, end: s.selectionEnd } : (s = (s.ownerDocument && s.ownerDocument.defaultView || window).getSelection(), s = { anchorNode: s.anchorNode, anchorOffset: s.anchorOffset, focusNode: s.focusNode, focusOffset: s.focusOffset }), As && Ns(As, s) || (As = s, s = Fs(Kd, "onSelect"), 0 < s.length && (r = new ft("onSelect", "select", null, r, o), n.push({ event: r, listeners: s }), r.target = ku)));
  }
  function Ms(n, r) {
    var o = {};
    return o[n.toLowerCase()] = r.toLowerCase(), o["Webkit" + n] = "webkit" + r, o["Moz" + n] = "moz" + r, o;
  }
  var Ou = { animationend: Ms("Animation", "AnimationEnd"), animationiteration: Ms("Animation", "AnimationIteration"), animationstart: Ms("Animation", "AnimationStart"), transitionend: Ms("Transition", "TransitionEnd") }, Kc = {}, jr = {};
  g && (jr = document.createElement("div").style, "AnimationEvent" in window || (delete Ou.animationend.animation, delete Ou.animationiteration.animation, delete Ou.animationstart.animation), "TransitionEvent" in window || delete Ou.transitionend.transition);
  function Ls(n) {
    if (Kc[n]) return Kc[n];
    if (!Ou[n]) return n;
    var r = Ou[n], o;
    for (o in r) if (r.hasOwnProperty(o) && o in jr) return Kc[n] = r[o];
    return n;
  }
  var _h = Ls("animationend"), kh = Ls("animationiteration"), Oh = Ls("animationstart"), Dh = Ls("transitionend"), Nh = /* @__PURE__ */ new Map(), Jd = "abort auxClick cancel canPlay canPlayThrough click close contextMenu copy cut drag dragEnd dragEnter dragExit dragLeave dragOver dragStart drop durationChange emptied encrypted ended error gotPointerCapture input invalid keyDown keyPress keyUp load loadedData loadedMetadata loadStart lostPointerCapture mouseDown mouseMove mouseOut mouseOver mouseUp paste pause play playing pointerCancel pointerDown pointerMove pointerOut pointerOver pointerUp progress rateChange reset resize seeked seeking stalled submit suspend timeUpdate touchCancel touchEnd touchStart volumeChange scroll toggle touchMove waiting wheel".split(" ");
  function $i(n, r) {
    Nh.set(n, r), T(r, [n]);
  }
  for (var Ol = 0; Ol < Jd.length; Ol++) {
    var Zd = Jd[Ol], zs = Zd.toLowerCase(), Lg = Zd[0].toUpperCase() + Zd.slice(1);
    $i(zs, "on" + Lg);
  }
  $i(_h, "onAnimationEnd"), $i(kh, "onAnimationIteration"), $i(Oh, "onAnimationStart"), $i("dblclick", "onDoubleClick"), $i("focusin", "onFocus"), $i("focusout", "onBlur"), $i(Dh, "onTransitionEnd"), _("onMouseEnter", ["mouseout", "mouseover"]), _("onMouseLeave", ["mouseout", "mouseover"]), _("onPointerEnter", ["pointerout", "pointerover"]), _("onPointerLeave", ["pointerout", "pointerover"]), T("onChange", "change click focusin focusout input keydown keyup selectionchange".split(" ")), T("onSelect", "focusout contextmenu dragend focusin keydown keyup mousedown mouseup selectionchange".split(" ")), T("onBeforeInput", ["compositionend", "keypress", "textInput", "paste"]), T("onCompositionEnd", "compositionend focusout keydown keypress keyup mousedown".split(" ")), T("onCompositionStart", "compositionstart focusout keydown keypress keyup mousedown".split(" ")), T("onCompositionUpdate", "compositionupdate focusout keydown keypress keyup mousedown".split(" "));
  var Us = "abort canplay canplaythrough durationchange emptied encrypted ended error loadeddata loadedmetadata loadstart pause play playing progress ratechange resize seeked seeking stalled suspend timeupdate volumechange waiting".split(" "), zg = new Set("cancel close invalid load scroll toggle".split(" ").concat(Us));
  function Xc(n, r, o) {
    var s = n.type || "unknown-event";
    n.currentTarget = o, Ae(s, r, void 0, n), n.currentTarget = null;
  }
  function Jc(n, r) {
    r = (r & 4) !== 0;
    for (var o = 0; o < n.length; o++) {
      var s = n[o], d = s.event;
      s = s.listeners;
      e: {
        var h = void 0;
        if (r) for (var b = s.length - 1; 0 <= b; b--) {
          var O = s[b], P = O.instance, J = O.currentTarget;
          if (O = O.listener, P !== h && d.isPropagationStopped()) break e;
          Xc(d, O, J), h = P;
        }
        else for (b = 0; b < s.length; b++) {
          if (O = s[b], P = O.instance, J = O.currentTarget, O = O.listener, P !== h && d.isPropagationStopped()) break e;
          Xc(d, O, J), h = P;
        }
      }
    }
    if (Ai) throw n = ro, Ai = !1, ro = null, n;
  }
  function Xt(n, r) {
    var o = r[np];
    o === void 0 && (o = r[np] = /* @__PURE__ */ new Set());
    var s = n + "__bubble";
    o.has(s) || (ep(r, n, 2, !1), o.add(s));
  }
  function Fo(n, r, o) {
    var s = 0;
    r && (s |= 4), ep(o, n, s, r);
  }
  var Ps = "_reactListening" + Math.random().toString(36).slice(2);
  function $s(n) {
    if (!n[Ps]) {
      n[Ps] = !0, y.forEach(function(o) {
        o !== "selectionchange" && (zg.has(o) || Fo(o, !1, n), Fo(o, !0, n));
      });
      var r = n.nodeType === 9 ? n : n.ownerDocument;
      r === null || r[Ps] || (r[Ps] = !0, Fo("selectionchange", !1, r));
    }
  }
  function ep(n, r, o, s) {
    switch (xs(r)) {
      case 1:
        var d = uo;
        break;
      case 4:
        d = Eu;
        break;
      default:
        d = Uo;
    }
    o = d.bind(null, r, o, n), d = void 0, !Da || r !== "touchstart" && r !== "touchmove" && r !== "wheel" || (d = !0), s ? d !== void 0 ? n.addEventListener(r, o, { capture: !0, passive: d }) : n.addEventListener(r, o, !0) : d !== void 0 ? n.addEventListener(r, o, { passive: d }) : n.addEventListener(r, o, !1);
  }
  function tp(n, r, o, s, d) {
    var h = s;
    if (!(r & 1) && !(r & 2) && s !== null) e: for (; ; ) {
      if (s === null) return;
      var b = s.tag;
      if (b === 3 || b === 4) {
        var O = s.stateNode.containerInfo;
        if (O === d || O.nodeType === 8 && O.parentNode === d) break;
        if (b === 4) for (b = s.return; b !== null; ) {
          var P = b.tag;
          if ((P === 3 || P === 4) && (P = b.stateNode.containerInfo, P === d || P.nodeType === 8 && P.parentNode === d)) return;
          b = b.return;
        }
        for (; O !== null; ) {
          if (b = Ml(O), b === null) return;
          if (P = b.tag, P === 5 || P === 6) {
            s = h = b;
            continue e;
          }
          O = O.parentNode;
        }
      }
      s = s.return;
    }
    Cl(function() {
      var J = h, ve = gn(o), he = [];
      e: {
        var pe = Nh.get(n);
        if (pe !== void 0) {
          var Ve = ft, Xe = n;
          switch (n) {
            case "keypress":
              if (K(o) === 0) break e;
            case "keydown":
            case "keyup":
              Ve = Yd;
              break;
            case "focusin":
              Xe = "focus", Ve = kl;
              break;
            case "focusout":
              Xe = "blur", Ve = kl;
              break;
            case "beforeblur":
            case "afterblur":
              Ve = kl;
              break;
            case "click":
              if (o.button === 2) break e;
            case "auxclick":
            case "dblclick":
            case "mousedown":
            case "mousemove":
            case "mouseup":
            case "mouseout":
            case "mouseover":
            case "contextmenu":
              Ve = Hn;
              break;
            case "drag":
            case "dragend":
            case "dragenter":
            case "dragexit":
            case "dragleave":
            case "dragover":
            case "dragstart":
            case "drop":
              Ve = _s;
              break;
            case "touchcancel":
            case "touchend":
            case "touchmove":
            case "touchstart":
              Ve = Gc;
              break;
            case _h:
            case kh:
            case Oh:
              Ve = Bd;
              break;
            case Dh:
              Ve = da;
              break;
            case "scroll":
              Ve = Kt;
              break;
            case "wheel":
              Ve = qn;
              break;
            case "copy":
            case "cut":
            case "paste":
              Ve = Id;
              break;
            case "gotpointercapture":
            case "lostpointercapture":
            case "pointercancel":
            case "pointerdown":
            case "pointermove":
            case "pointerout":
            case "pointerover":
            case "pointerup":
              Ve = Wc;
          }
          var Ze = (r & 4) !== 0, Yn = !Ze && n === "scroll", Y = Ze ? pe !== null ? pe + "Capture" : null : pe;
          Ze = [];
          for (var H = J, Q; H !== null; ) {
            Q = H;
            var Se = Q.stateNode;
            if (Q.tag === 5 && Se !== null && (Q = Se, Y !== null && (Se = Di(H, Y), Se != null && Ze.push(Du(H, Se, Q)))), Yn) break;
            H = H.return;
          }
          0 < Ze.length && (pe = new Ve(pe, Xe, null, o, ve), he.push({ event: pe, listeners: Ze }));
        }
      }
      if (!(r & 7)) {
        e: {
          if (pe = n === "mouseover" || n === "pointerover", Ve = n === "mouseout" || n === "pointerout", pe && o !== vr && (Xe = o.relatedTarget || o.fromElement) && (Ml(Xe) || Xe[vo])) break e;
          if ((Ve || pe) && (pe = ve.window === ve ? ve : (pe = ve.ownerDocument) ? pe.defaultView || pe.parentWindow : window, Ve ? (Xe = o.relatedTarget || o.toElement, Ve = J, Xe = Xe ? Ml(Xe) : null, Xe !== null && (Yn = Ue(Xe), Xe !== Yn || Xe.tag !== 5 && Xe.tag !== 6) && (Xe = null)) : (Ve = null, Xe = J), Ve !== Xe)) {
            if (Ze = Hn, Se = "onMouseLeave", Y = "onMouseEnter", H = "mouse", (n === "pointerout" || n === "pointerover") && (Ze = Wc, Se = "onPointerLeave", Y = "onPointerEnter", H = "pointer"), Yn = Ve == null ? pe : nt(Ve), Q = Xe == null ? pe : nt(Xe), pe = new Ze(Se, H + "leave", Ve, o, ve), pe.target = Yn, pe.relatedTarget = Q, Se = null, Ml(ve) === J && (Ze = new Ze(Y, H + "enter", Xe, o, ve), Ze.target = Q, Ze.relatedTarget = Yn, Se = Ze), Yn = Se, Ve && Xe) t: {
              for (Ze = Ve, Y = Xe, H = 0, Q = Ze; Q; Q = Dl(Q)) H++;
              for (Q = 0, Se = Y; Se; Se = Dl(Se)) Q++;
              for (; 0 < H - Q; ) Ze = Dl(Ze), H--;
              for (; 0 < Q - H; ) Y = Dl(Y), Q--;
              for (; H--; ) {
                if (Ze === Y || Y !== null && Ze === Y.alternate) break t;
                Ze = Dl(Ze), Y = Dl(Y);
              }
              Ze = null;
            }
            else Ze = null;
            Ve !== null && Zc(he, pe, Ve, Ze, !1), Xe !== null && Yn !== null && Zc(he, Yn, Xe, Ze, !0);
          }
        }
        e: {
          if (pe = J ? nt(J) : window, Ve = pe.nodeName && pe.nodeName.toLowerCase(), Ve === "select" || Ve === "input" && pe.type === "file") var $e = mh;
          else if (vh(pe)) if (yh) $e = Mg;
          else {
            $e = Ag;
            var at = Ng;
          }
          else (Ve = pe.nodeName) && Ve.toLowerCase() === "input" && (pe.type === "checkbox" || pe.type === "radio") && ($e = Ch);
          if ($e && ($e = $e(n, J))) {
            hh(he, $e, o, ve);
            break e;
          }
          at && at(n, pe, J), n === "focusout" && (at = pe._wrapperState) && at.controlled && pe.type === "number" && di(pe, "number", pe.value);
        }
        switch (at = J ? nt(J) : window, n) {
          case "focusin":
            (vh(at) || at.contentEditable === "true") && (ku = at, Kd = J, As = null);
            break;
          case "focusout":
            As = Kd = ku = null;
            break;
          case "mousedown":
            Xd = !0;
            break;
          case "contextmenu":
          case "mouseup":
          case "dragend":
            Xd = !1, xh(he, o, ve);
            break;
          case "selectionchange":
            if (_u) break;
          case "keydown":
          case "keyup":
            xh(he, o, ve);
        }
        var st;
        if (Os) e: {
          switch (n) {
            case "compositionstart":
              var mt = "onCompositionStart";
              break e;
            case "compositionend":
              mt = "onCompositionEnd";
              break e;
            case "compositionupdate":
              mt = "onCompositionUpdate";
              break e;
          }
          mt = void 0;
        }
        else Ru ? Qc(n, o) && (mt = "onCompositionEnd") : n === "keydown" && o.keyCode === 229 && (mt = "onCompositionStart");
        mt && (Tu && o.locale !== "ko" && (Ru || mt !== "onCompositionStart" ? mt === "onCompositionEnd" && Ru && (st = D()) : (qa = ve, bu = "value" in qa ? qa.value : qa.textContent, Ru = !0)), at = Fs(J, mt), 0 < at.length && (mt = new Yc(mt, n, null, o, ve), he.push({ event: mt, listeners: at }), st ? mt.data = st : (st = dh(o), st !== null && (mt.data = st)))), (st = kg ? Og(n, o) : ph(n, o)) && (J = Fs(J, "onBeforeInput"), 0 < J.length && (ve = new Yc("onBeforeInput", "beforeinput", null, o, ve), he.push({ event: ve, listeners: J }), ve.data = st));
      }
      Jc(he, r);
    });
  }
  function Du(n, r, o) {
    return { instance: n, listener: r, currentTarget: o };
  }
  function Fs(n, r) {
    for (var o = r + "Capture", s = []; n !== null; ) {
      var d = n, h = d.stateNode;
      d.tag === 5 && h !== null && (d = h, h = Di(n, o), h != null && s.unshift(Du(n, h, d)), h = Di(n, r), h != null && s.push(Du(n, h, d))), n = n.return;
    }
    return s;
  }
  function Dl(n) {
    if (n === null) return null;
    do
      n = n.return;
    while (n && n.tag !== 5);
    return n || null;
  }
  function Zc(n, r, o, s, d) {
    for (var h = r._reactName, b = []; o !== null && o !== s; ) {
      var O = o, P = O.alternate, J = O.stateNode;
      if (P !== null && P === s) break;
      O.tag === 5 && J !== null && (O = J, d ? (P = Di(o, h), P != null && b.unshift(Du(o, P, O))) : d || (P = Di(o, h), P != null && b.push(Du(o, P, O)))), o = o.return;
    }
    b.length !== 0 && n.push({ event: r, listeners: b });
  }
  var Ug = /\r\n?/g, Ah = /\u0000|\uFFFD/g;
  function Mh(n) {
    return (typeof n == "string" ? n : "" + n).replace(Ug, `
`).replace(Ah, "");
  }
  function ef(n, r, o) {
    if (r = Mh(r), Mh(n) !== r && o) throw Error(v(425));
  }
  function tf() {
  }
  var Nl = null, js = null;
  function Al(n, r) {
    return n === "textarea" || n === "noscript" || typeof r.children == "string" || typeof r.children == "number" || typeof r.dangerouslySetInnerHTML == "object" && r.dangerouslySetInnerHTML !== null && r.dangerouslySetInnerHTML.__html != null;
  }
  var nf = typeof setTimeout == "function" ? setTimeout : void 0, Lh = typeof clearTimeout == "function" ? clearTimeout : void 0, rf = typeof Promise == "function" ? Promise : void 0, Pg = typeof queueMicrotask == "function" ? queueMicrotask : typeof rf < "u" ? function(n) {
    return rf.resolve(null).then(n).catch(Nu);
  } : nf;
  function Nu(n) {
    setTimeout(function() {
      throw n;
    });
  }
  function Au(n, r) {
    var o = r, s = 0;
    do {
      var d = o.nextSibling;
      if (n.removeChild(o), d && d.nodeType === 8) if (o = d.data, o === "/$") {
        if (s === 0) {
          n.removeChild(d), Ga(r);
          return;
        }
        s--;
      } else o !== "$" && o !== "$?" && o !== "$!" || s++;
      o = d;
    } while (o);
    Ga(r);
  }
  function gi(n) {
    for (; n != null; n = n.nextSibling) {
      var r = n.nodeType;
      if (r === 1 || r === 3) break;
      if (r === 8) {
        if (r = n.data, r === "$" || r === "$!" || r === "$?") break;
        if (r === "/$") return null;
      }
    }
    return n;
  }
  function af(n) {
    n = n.previousSibling;
    for (var r = 0; n; ) {
      if (n.nodeType === 8) {
        var o = n.data;
        if (o === "$" || o === "$!" || o === "$?") {
          if (r === 0) return n;
          r--;
        } else o === "/$" && r++;
      }
      n = n.previousSibling;
    }
    return null;
  }
  var Mu = Math.random().toString(36).slice(2), Ka = "__reactFiber$" + Mu, Hs = "__reactProps$" + Mu, vo = "__reactContainer$" + Mu, np = "__reactEvents$" + Mu, rp = "__reactListeners$" + Mu, Lu = "__reactHandles$" + Mu;
  function Ml(n) {
    var r = n[Ka];
    if (r) return r;
    for (var o = n.parentNode; o; ) {
      if (r = o[vo] || o[Ka]) {
        if (o = r.alternate, r.child !== null || o !== null && o.child !== null) for (n = af(n); n !== null; ) {
          if (o = n[Ka]) return o;
          n = af(n);
        }
        return r;
      }
      n = o, o = n.parentNode;
    }
    return null;
  }
  function Vs(n) {
    return n = n[Ka] || n[vo], !n || n.tag !== 5 && n.tag !== 6 && n.tag !== 13 && n.tag !== 3 ? null : n;
  }
  function nt(n) {
    if (n.tag === 5 || n.tag === 6) return n.stateNode;
    throw Error(v(33));
  }
  function ho(n) {
    return n[Hs] || null;
  }
  var Kn = [], At = -1;
  function pa(n) {
    return { current: n };
  }
  function sn(n) {
    0 > At || (n.current = Kn[At], Kn[At] = null, At--);
  }
  function mn(n, r) {
    At++, Kn[At] = n.current, n.current = r;
  }
  var Ot = {}, Un = pa(Ot), Xn = pa(!1), Xa = Ot;
  function Aa(n, r) {
    var o = n.type.contextTypes;
    if (!o) return Ot;
    var s = n.stateNode;
    if (s && s.__reactInternalMemoizedUnmaskedChildContext === r) return s.__reactInternalMemoizedMaskedChildContext;
    var d = {}, h;
    for (h in o) d[h] = r[h];
    return s && (n = n.stateNode, n.__reactInternalMemoizedUnmaskedChildContext = r, n.__reactInternalMemoizedMaskedChildContext = d), d;
  }
  function Jn(n) {
    return n = n.childContextTypes, n != null;
  }
  function Fi() {
    sn(Xn), sn(Un);
  }
  function of(n, r, o) {
    if (Un.current !== Ot) throw Error(v(168));
    mn(Un, r), mn(Xn, o);
  }
  function zh(n, r, o) {
    var s = n.stateNode;
    if (r = r.childContextTypes, typeof s.getChildContext != "function") return o;
    s = s.getChildContext();
    for (var d in s) if (!(d in r)) throw Error(v(108, ze(n) || "Unknown", d));
    return ke({}, o, s);
  }
  function Ll(n) {
    return n = (n = n.stateNode) && n.__reactInternalMemoizedMergedChildContext || Ot, Xa = Un.current, mn(Un, n), mn(Xn, Xn.current), !0;
  }
  function Ja(n, r, o) {
    var s = n.stateNode;
    if (!s) throw Error(v(169));
    o ? (n = zh(n, r, Xa), s.__reactInternalMemoizedMergedChildContext = n, sn(Xn), sn(Un), mn(Un, n)) : sn(Xn), mn(Xn, o);
  }
  var Si = null, Bs = !1, Is = !1;
  function jo(n) {
    Si === null ? Si = [n] : Si.push(n);
  }
  function ap(n) {
    Bs = !0, jo(n);
  }
  function Qr() {
    if (!Is && Si !== null) {
      Is = !0;
      var n = 0, r = Pt;
      try {
        var o = Si;
        for (Pt = 1; n < o.length; n++) {
          var s = o[n];
          do
            s = s(!0);
          while (s !== null);
        }
        Si = null, Bs = !1;
      } catch (d) {
        throw Si !== null && (Si = Si.slice(n + 1)), Sn(Et, Qr), d;
      } finally {
        Pt = r, Is = !1;
      }
    }
    return null;
  }
  var Ho = [], Vo = 0, zu = null, Bo = 0, Rr = [], Zn = 0, zl = null, qr = 1, ji = "";
  function Io(n, r) {
    Ho[Vo++] = Bo, Ho[Vo++] = zu, zu = n, Bo = r;
  }
  function Uh(n, r, o) {
    Rr[Zn++] = qr, Rr[Zn++] = ji, Rr[Zn++] = zl, zl = n;
    var s = qr;
    n = ji;
    var d = 32 - Yr(s) - 1;
    s &= ~(1 << d), o += 1;
    var h = 32 - Yr(r) + d;
    if (30 < h) {
      var b = d - d % 5;
      h = (s & (1 << b) - 1).toString(32), s >>= b, d -= b, qr = 1 << 32 - Yr(r) + d | o << d | s, ji = h + n;
    } else qr = 1 << h | o << d | s, ji = n;
  }
  function ip(n) {
    n.return !== null && (Io(n, 1), Uh(n, 1, 0));
  }
  function lf(n) {
    for (; n === zu; ) zu = Ho[--Vo], Ho[Vo] = null, Bo = Ho[--Vo], Ho[Vo] = null;
    for (; n === zl; ) zl = Rr[--Zn], Rr[Zn] = null, ji = Rr[--Zn], Rr[Zn] = null, qr = Rr[--Zn], Rr[Zn] = null;
  }
  var va = null, ha = null, xn = !1, Ei = null;
  function op(n, r) {
    var o = ri(5, null, null, 0);
    o.elementType = "DELETED", o.stateNode = r, o.return = n, r = n.deletions, r === null ? (n.deletions = [o], n.flags |= 16) : r.push(o);
  }
  function lp(n, r) {
    switch (n.tag) {
      case 5:
        var o = n.type;
        return r = r.nodeType !== 1 || o.toLowerCase() !== r.nodeName.toLowerCase() ? null : r, r !== null ? (n.stateNode = r, va = n, ha = gi(r.firstChild), !0) : !1;
      case 6:
        return r = n.pendingProps === "" || r.nodeType !== 3 ? null : r, r !== null ? (n.stateNode = r, va = n, ha = null, !0) : !1;
      case 13:
        return r = r.nodeType !== 8 ? null : r, r !== null ? (o = zl !== null ? { id: qr, overflow: ji } : null, n.memoizedState = { dehydrated: r, treeContext: o, retryLane: 1073741824 }, o = ri(18, null, null, 0), o.stateNode = r, o.return = n, n.child = o, va = n, ha = null, !0) : !1;
      default:
        return !1;
    }
  }
  function up(n) {
    return (n.mode & 1) !== 0 && (n.flags & 128) === 0;
  }
  function sp(n) {
    if (xn) {
      var r = ha;
      if (r) {
        var o = r;
        if (!lp(n, r)) {
          if (up(n)) throw Error(v(418));
          r = gi(o.nextSibling);
          var s = va;
          r && lp(n, r) ? op(s, o) : (n.flags = n.flags & -4097 | 2, xn = !1, va = n);
        }
      } else {
        if (up(n)) throw Error(v(418));
        n.flags = n.flags & -4097 | 2, xn = !1, va = n;
      }
    }
  }
  function Ph(n) {
    for (n = n.return; n !== null && n.tag !== 5 && n.tag !== 3 && n.tag !== 13; ) n = n.return;
    va = n;
  }
  function Vn(n) {
    if (n !== va) return !1;
    if (!xn) return Ph(n), xn = !0, !1;
    var r;
    if ((r = n.tag !== 3) && !(r = n.tag !== 5) && (r = n.type, r = r !== "head" && r !== "body" && !Al(n.type, n.memoizedProps)), r && (r = ha)) {
      if (up(n)) throw $h(), Error(v(418));
      for (; r; ) op(n, r), r = gi(r.nextSibling);
    }
    if (Ph(n), n.tag === 13) {
      if (n = n.memoizedState, n = n !== null ? n.dehydrated : null, !n) throw Error(v(317));
      e: {
        for (n = n.nextSibling, r = 0; n; ) {
          if (n.nodeType === 8) {
            var o = n.data;
            if (o === "/$") {
              if (r === 0) {
                ha = gi(n.nextSibling);
                break e;
              }
              r--;
            } else o !== "$" && o !== "$!" && o !== "$?" || r++;
          }
          n = n.nextSibling;
        }
        ha = null;
      }
    } else ha = va ? gi(n.stateNode.nextSibling) : null;
    return !0;
  }
  function $h() {
    for (var n = ha; n; ) n = gi(n.nextSibling);
  }
  function mo() {
    ha = va = null, xn = !1;
  }
  function Ys(n) {
    Ei === null ? Ei = [n] : Ei.push(n);
  }
  var Ul = ue.ReactCurrentBatchConfig;
  function Ws(n, r, o) {
    if (n = o.ref, n !== null && typeof n != "function" && typeof n != "object") {
      if (o._owner) {
        if (o = o._owner, o) {
          if (o.tag !== 1) throw Error(v(309));
          var s = o.stateNode;
        }
        if (!s) throw Error(v(147, n));
        var d = s, h = "" + n;
        return r !== null && r.ref !== null && typeof r.ref == "function" && r.ref._stringRef === h ? r.ref : (r = function(b) {
          var O = d.refs;
          b === null ? delete O[h] : O[h] = b;
        }, r._stringRef = h, r);
      }
      if (typeof n != "string") throw Error(v(284));
      if (!o._owner) throw Error(v(290, n));
    }
    return n;
  }
  function Uu(n, r) {
    throw n = Object.prototype.toString.call(r), Error(v(31, n === "[object Object]" ? "object with keys {" + Object.keys(r).join(", ") + "}" : n));
  }
  function Fh(n) {
    var r = n._init;
    return r(n._payload);
  }
  function jh(n) {
    function r(Y, H) {
      if (n) {
        var Q = Y.deletions;
        Q === null ? (Y.deletions = [H], Y.flags |= 16) : Q.push(H);
      }
    }
    function o(Y, H) {
      if (!n) return null;
      for (; H !== null; ) r(Y, H), H = H.sibling;
      return null;
    }
    function s(Y, H) {
      for (Y = /* @__PURE__ */ new Map(); H !== null; ) H.key !== null ? Y.set(H.key, H) : Y.set(H.index, H), H = H.sibling;
      return Y;
    }
    function d(Y, H) {
      return Y = tl(Y, H), Y.index = 0, Y.sibling = null, Y;
    }
    function h(Y, H, Q) {
      return Y.index = Q, n ? (Q = Y.alternate, Q !== null ? (Q = Q.index, Q < H ? (Y.flags |= 2, H) : Q) : (Y.flags |= 2, H)) : (Y.flags |= 1048576, H);
    }
    function b(Y) {
      return n && Y.alternate === null && (Y.flags |= 2), Y;
    }
    function O(Y, H, Q, Se) {
      return H === null || H.tag !== 6 ? (H = Zl(Q, Y.mode, Se), H.return = Y, H) : (H = d(H, Q), H.return = Y, H);
    }
    function P(Y, H, Q, Se) {
      var $e = Q.type;
      return $e === Ce ? ve(Y, H, Q.props.children, Se, Q.key) : H !== null && (H.elementType === $e || typeof $e == "object" && $e !== null && $e.$$typeof === vt && Fh($e) === H.type) ? (Se = d(H, Q.props), Se.ref = Ws(Y, H, Q), Se.return = Y, Se) : (Se = Wf(Q.type, Q.key, Q.props, null, Y.mode, Se), Se.ref = Ws(Y, H, Q), Se.return = Y, Se);
    }
    function J(Y, H, Q, Se) {
      return H === null || H.tag !== 4 || H.stateNode.containerInfo !== Q.containerInfo || H.stateNode.implementation !== Q.implementation ? (H = jp(Q, Y.mode, Se), H.return = Y, H) : (H = d(H, Q.children || []), H.return = Y, H);
    }
    function ve(Y, H, Q, Se, $e) {
      return H === null || H.tag !== 7 ? (H = nl(Q, Y.mode, Se, $e), H.return = Y, H) : (H = d(H, Q), H.return = Y, H);
    }
    function he(Y, H, Q) {
      if (typeof H == "string" && H !== "" || typeof H == "number") return H = Zl("" + H, Y.mode, Q), H.return = Y, H;
      if (typeof H == "object" && H !== null) {
        switch (H.$$typeof) {
          case q:
            return Q = Wf(H.type, H.key, H.props, null, Y.mode, Q), Q.ref = Ws(Y, null, H), Q.return = Y, Q;
          case se:
            return H = jp(H, Y.mode, Q), H.return = Y, H;
          case vt:
            var Se = H._init;
            return he(Y, Se(H._payload), Q);
        }
        if (Ir(H) || Ie(H)) return H = nl(H, Y.mode, Q, null), H.return = Y, H;
        Uu(Y, H);
      }
      return null;
    }
    function pe(Y, H, Q, Se) {
      var $e = H !== null ? H.key : null;
      if (typeof Q == "string" && Q !== "" || typeof Q == "number") return $e !== null ? null : O(Y, H, "" + Q, Se);
      if (typeof Q == "object" && Q !== null) {
        switch (Q.$$typeof) {
          case q:
            return Q.key === $e ? P(Y, H, Q, Se) : null;
          case se:
            return Q.key === $e ? J(Y, H, Q, Se) : null;
          case vt:
            return $e = Q._init, pe(
              Y,
              H,
              $e(Q._payload),
              Se
            );
        }
        if (Ir(Q) || Ie(Q)) return $e !== null ? null : ve(Y, H, Q, Se, null);
        Uu(Y, Q);
      }
      return null;
    }
    function Ve(Y, H, Q, Se, $e) {
      if (typeof Se == "string" && Se !== "" || typeof Se == "number") return Y = Y.get(Q) || null, O(H, Y, "" + Se, $e);
      if (typeof Se == "object" && Se !== null) {
        switch (Se.$$typeof) {
          case q:
            return Y = Y.get(Se.key === null ? Q : Se.key) || null, P(H, Y, Se, $e);
          case se:
            return Y = Y.get(Se.key === null ? Q : Se.key) || null, J(H, Y, Se, $e);
          case vt:
            var at = Se._init;
            return Ve(Y, H, Q, at(Se._payload), $e);
        }
        if (Ir(Se) || Ie(Se)) return Y = Y.get(Q) || null, ve(H, Y, Se, $e, null);
        Uu(H, Se);
      }
      return null;
    }
    function Xe(Y, H, Q, Se) {
      for (var $e = null, at = null, st = H, mt = H = 0, sr = null; st !== null && mt < Q.length; mt++) {
        st.index > mt ? (sr = st, st = null) : sr = st.sibling;
        var Bt = pe(Y, st, Q[mt], Se);
        if (Bt === null) {
          st === null && (st = sr);
          break;
        }
        n && st && Bt.alternate === null && r(Y, st), H = h(Bt, H, mt), at === null ? $e = Bt : at.sibling = Bt, at = Bt, st = sr;
      }
      if (mt === Q.length) return o(Y, st), xn && Io(Y, mt), $e;
      if (st === null) {
        for (; mt < Q.length; mt++) st = he(Y, Q[mt], Se), st !== null && (H = h(st, H, mt), at === null ? $e = st : at.sibling = st, at = st);
        return xn && Io(Y, mt), $e;
      }
      for (st = s(Y, st); mt < Q.length; mt++) sr = Ve(st, Y, mt, Q[mt], Se), sr !== null && (n && sr.alternate !== null && st.delete(sr.key === null ? mt : sr.key), H = h(sr, H, mt), at === null ? $e = sr : at.sibling = sr, at = sr);
      return n && st.forEach(function(al) {
        return r(Y, al);
      }), xn && Io(Y, mt), $e;
    }
    function Ze(Y, H, Q, Se) {
      var $e = Ie(Q);
      if (typeof $e != "function") throw Error(v(150));
      if (Q = $e.call(Q), Q == null) throw Error(v(151));
      for (var at = $e = null, st = H, mt = H = 0, sr = null, Bt = Q.next(); st !== null && !Bt.done; mt++, Bt = Q.next()) {
        st.index > mt ? (sr = st, st = null) : sr = st.sibling;
        var al = pe(Y, st, Bt.value, Se);
        if (al === null) {
          st === null && (st = sr);
          break;
        }
        n && st && al.alternate === null && r(Y, st), H = h(al, H, mt), at === null ? $e = al : at.sibling = al, at = al, st = sr;
      }
      if (Bt.done) return o(
        Y,
        st
      ), xn && Io(Y, mt), $e;
      if (st === null) {
        for (; !Bt.done; mt++, Bt = Q.next()) Bt = he(Y, Bt.value, Se), Bt !== null && (H = h(Bt, H, mt), at === null ? $e = Bt : at.sibling = Bt, at = Bt);
        return xn && Io(Y, mt), $e;
      }
      for (st = s(Y, st); !Bt.done; mt++, Bt = Q.next()) Bt = Ve(st, Y, mt, Bt.value, Se), Bt !== null && (n && Bt.alternate !== null && st.delete(Bt.key === null ? mt : Bt.key), H = h(Bt, H, mt), at === null ? $e = Bt : at.sibling = Bt, at = Bt);
      return n && st.forEach(function(Xg) {
        return r(Y, Xg);
      }), xn && Io(Y, mt), $e;
    }
    function Yn(Y, H, Q, Se) {
      if (typeof Q == "object" && Q !== null && Q.type === Ce && Q.key === null && (Q = Q.props.children), typeof Q == "object" && Q !== null) {
        switch (Q.$$typeof) {
          case q:
            e: {
              for (var $e = Q.key, at = H; at !== null; ) {
                if (at.key === $e) {
                  if ($e = Q.type, $e === Ce) {
                    if (at.tag === 7) {
                      o(Y, at.sibling), H = d(at, Q.props.children), H.return = Y, Y = H;
                      break e;
                    }
                  } else if (at.elementType === $e || typeof $e == "object" && $e !== null && $e.$$typeof === vt && Fh($e) === at.type) {
                    o(Y, at.sibling), H = d(at, Q.props), H.ref = Ws(Y, at, Q), H.return = Y, Y = H;
                    break e;
                  }
                  o(Y, at);
                  break;
                } else r(Y, at);
                at = at.sibling;
              }
              Q.type === Ce ? (H = nl(Q.props.children, Y.mode, Se, Q.key), H.return = Y, Y = H) : (Se = Wf(Q.type, Q.key, Q.props, null, Y.mode, Se), Se.ref = Ws(Y, H, Q), Se.return = Y, Y = Se);
            }
            return b(Y);
          case se:
            e: {
              for (at = Q.key; H !== null; ) {
                if (H.key === at) if (H.tag === 4 && H.stateNode.containerInfo === Q.containerInfo && H.stateNode.implementation === Q.implementation) {
                  o(Y, H.sibling), H = d(H, Q.children || []), H.return = Y, Y = H;
                  break e;
                } else {
                  o(Y, H);
                  break;
                }
                else r(Y, H);
                H = H.sibling;
              }
              H = jp(Q, Y.mode, Se), H.return = Y, Y = H;
            }
            return b(Y);
          case vt:
            return at = Q._init, Yn(Y, H, at(Q._payload), Se);
        }
        if (Ir(Q)) return Xe(Y, H, Q, Se);
        if (Ie(Q)) return Ze(Y, H, Q, Se);
        Uu(Y, Q);
      }
      return typeof Q == "string" && Q !== "" || typeof Q == "number" ? (Q = "" + Q, H !== null && H.tag === 6 ? (o(Y, H.sibling), H = d(H, Q), H.return = Y, Y = H) : (o(Y, H), H = Zl(Q, Y.mode, Se), H.return = Y, Y = H), b(Y)) : o(Y, H);
    }
    return Yn;
  }
  var Ci = jh(!0), wr = jh(!1), Ne = pa(null), Ma = null, Hr = null, cp = null;
  function fp() {
    cp = Hr = Ma = null;
  }
  function dp(n) {
    var r = Ne.current;
    sn(Ne), n._currentValue = r;
  }
  function pp(n, r, o) {
    for (; n !== null; ) {
      var s = n.alternate;
      if ((n.childLanes & r) !== r ? (n.childLanes |= r, s !== null && (s.childLanes |= r)) : s !== null && (s.childLanes & r) !== r && (s.childLanes |= r), n === o) break;
      n = n.return;
    }
  }
  function Pu(n, r) {
    Ma = n, cp = Hr = null, n = n.dependencies, n !== null && n.firstContext !== null && (n.lanes & r && (gr = !0), n.firstContext = null);
  }
  function en(n) {
    var r = n._currentValue;
    if (cp !== n) if (n = { context: n, memoizedValue: r, next: null }, Hr === null) {
      if (Ma === null) throw Error(v(308));
      Hr = n, Ma.dependencies = { lanes: 0, firstContext: n };
    } else Hr = Hr.next = n;
    return r;
  }
  var Pl = null;
  function vp(n) {
    Pl === null ? Pl = [n] : Pl.push(n);
  }
  function Hh(n, r, o, s) {
    var d = r.interleaved;
    return d === null ? (o.next = o, vp(r)) : (o.next = d.next, d.next = o), r.interleaved = o, Hi(n, s);
  }
  function Hi(n, r) {
    n.lanes |= r;
    var o = n.alternate;
    for (o !== null && (o.lanes |= r), o = n, n = n.return; n !== null; ) n.childLanes |= r, o = n.alternate, o !== null && (o.childLanes |= r), o = n, n = n.return;
    return o.tag === 3 ? o.stateNode : null;
  }
  var Za = !1;
  function Yo(n) {
    n.updateQueue = { baseState: n.memoizedState, firstBaseUpdate: null, lastBaseUpdate: null, shared: { pending: null, interleaved: null, lanes: 0 }, effects: null };
  }
  function Vh(n, r) {
    n = n.updateQueue, r.updateQueue === n && (r.updateQueue = { baseState: n.baseState, firstBaseUpdate: n.firstBaseUpdate, lastBaseUpdate: n.lastBaseUpdate, shared: n.shared, effects: n.effects });
  }
  function yo(n, r) {
    return { eventTime: n, lane: r, tag: 0, payload: null, callback: null, next: null };
  }
  function Wo(n, r, o) {
    var s = n.updateQueue;
    if (s === null) return null;
    if (s = s.shared, Mt & 2) {
      var d = s.pending;
      return d === null ? r.next = r : (r.next = d.next, d.next = r), s.pending = r, Hi(n, o);
    }
    return d = s.interleaved, d === null ? (r.next = r, vp(s)) : (r.next = d.next, d.next = r), s.interleaved = r, Hi(n, o);
  }
  function uf(n, r, o) {
    if (r = r.updateQueue, r !== null && (r = r.shared, (o & 4194240) !== 0)) {
      var s = r.lanes;
      s &= n.pendingLanes, o |= s, r.lanes = o, Rs(n, o);
    }
  }
  function Bh(n, r) {
    var o = n.updateQueue, s = n.alternate;
    if (s !== null && (s = s.updateQueue, o === s)) {
      var d = null, h = null;
      if (o = o.firstBaseUpdate, o !== null) {
        do {
          var b = { eventTime: o.eventTime, lane: o.lane, tag: o.tag, payload: o.payload, callback: o.callback, next: null };
          h === null ? d = h = b : h = h.next = b, o = o.next;
        } while (o !== null);
        h === null ? d = h = r : h = h.next = r;
      } else d = h = r;
      o = { baseState: s.baseState, firstBaseUpdate: d, lastBaseUpdate: h, shared: s.shared, effects: s.effects }, n.updateQueue = o;
      return;
    }
    n = o.lastBaseUpdate, n === null ? o.firstBaseUpdate = r : n.next = r, o.lastBaseUpdate = r;
  }
  function sf(n, r, o, s) {
    var d = n.updateQueue;
    Za = !1;
    var h = d.firstBaseUpdate, b = d.lastBaseUpdate, O = d.shared.pending;
    if (O !== null) {
      d.shared.pending = null;
      var P = O, J = P.next;
      P.next = null, b === null ? h = J : b.next = J, b = P;
      var ve = n.alternate;
      ve !== null && (ve = ve.updateQueue, O = ve.lastBaseUpdate, O !== b && (O === null ? ve.firstBaseUpdate = J : O.next = J, ve.lastBaseUpdate = P));
    }
    if (h !== null) {
      var he = d.baseState;
      b = 0, ve = J = P = null, O = h;
      do {
        var pe = O.lane, Ve = O.eventTime;
        if ((s & pe) === pe) {
          ve !== null && (ve = ve.next = {
            eventTime: Ve,
            lane: 0,
            tag: O.tag,
            payload: O.payload,
            callback: O.callback,
            next: null
          });
          e: {
            var Xe = n, Ze = O;
            switch (pe = r, Ve = o, Ze.tag) {
              case 1:
                if (Xe = Ze.payload, typeof Xe == "function") {
                  he = Xe.call(Ve, he, pe);
                  break e;
                }
                he = Xe;
                break e;
              case 3:
                Xe.flags = Xe.flags & -65537 | 128;
              case 0:
                if (Xe = Ze.payload, pe = typeof Xe == "function" ? Xe.call(Ve, he, pe) : Xe, pe == null) break e;
                he = ke({}, he, pe);
                break e;
              case 2:
                Za = !0;
            }
          }
          O.callback !== null && O.lane !== 0 && (n.flags |= 64, pe = d.effects, pe === null ? d.effects = [O] : pe.push(O));
        } else Ve = { eventTime: Ve, lane: pe, tag: O.tag, payload: O.payload, callback: O.callback, next: null }, ve === null ? (J = ve = Ve, P = he) : ve = ve.next = Ve, b |= pe;
        if (O = O.next, O === null) {
          if (O = d.shared.pending, O === null) break;
          pe = O, O = pe.next, pe.next = null, d.lastBaseUpdate = pe, d.shared.pending = null;
        }
      } while (!0);
      if (ve === null && (P = he), d.baseState = P, d.firstBaseUpdate = J, d.lastBaseUpdate = ve, r = d.shared.interleaved, r !== null) {
        d = r;
        do
          b |= d.lane, d = d.next;
        while (d !== r);
      } else h === null && (d.shared.lanes = 0);
      Gl |= b, n.lanes = b, n.memoizedState = he;
    }
  }
  function hp(n, r, o) {
    if (n = r.effects, r.effects = null, n !== null) for (r = 0; r < n.length; r++) {
      var s = n[r], d = s.callback;
      if (d !== null) {
        if (s.callback = null, s = o, typeof d != "function") throw Error(v(191, d));
        d.call(s);
      }
    }
  }
  var $u = {}, Vi = pa($u), Gs = pa($u), Qs = pa($u);
  function $l(n) {
    if (n === $u) throw Error(v(174));
    return n;
  }
  function mp(n, r) {
    switch (mn(Qs, r), mn(Gs, n), mn(Vi, $u), n = r.nodeType, n) {
      case 9:
      case 11:
        r = (r = r.documentElement) ? r.namespaceURI : br(null, "");
        break;
      default:
        n = n === 8 ? r.parentNode : r, r = n.namespaceURI || null, n = n.tagName, r = br(r, n);
    }
    sn(Vi), mn(Vi, r);
  }
  function Fu() {
    sn(Vi), sn(Gs), sn(Qs);
  }
  function yp(n) {
    $l(Qs.current);
    var r = $l(Vi.current), o = br(r, n.type);
    r !== o && (mn(Gs, n), mn(Vi, o));
  }
  function gp(n) {
    Gs.current === n && (sn(Vi), sn(Gs));
  }
  var Nn = pa(0);
  function cf(n) {
    for (var r = n; r !== null; ) {
      if (r.tag === 13) {
        var o = r.memoizedState;
        if (o !== null && (o = o.dehydrated, o === null || o.data === "$?" || o.data === "$!")) return r;
      } else if (r.tag === 19 && r.memoizedProps.revealOrder !== void 0) {
        if (r.flags & 128) return r;
      } else if (r.child !== null) {
        r.child.return = r, r = r.child;
        continue;
      }
      if (r === n) break;
      for (; r.sibling === null; ) {
        if (r.return === null || r.return === n) return null;
        r = r.return;
      }
      r.sibling.return = r.return, r = r.sibling;
    }
    return null;
  }
  var Sp = [];
  function qs() {
    for (var n = 0; n < Sp.length; n++) Sp[n]._workInProgressVersionPrimary = null;
    Sp.length = 0;
  }
  var rt = ue.ReactCurrentDispatcher, Dt = ue.ReactCurrentBatchConfig, zt = 0, Ct = null, cn = null, or = null, ff = !1, Ks = !1, Xs = 0, Ep = 0;
  function oe() {
    throw Error(v(321));
  }
  function er(n, r) {
    if (r === null) return !1;
    for (var o = 0; o < r.length && o < n.length; o++) if (!yi(n[o], r[o])) return !1;
    return !0;
  }
  function ct(n, r, o, s, d, h) {
    if (zt = h, Ct = r, r.memoizedState = null, r.updateQueue = null, r.lanes = 0, rt.current = n === null || n.memoizedState === null ? xf : _f, n = o(s, d), Ks) {
      h = 0;
      do {
        if (Ks = !1, Xs = 0, 25 <= h) throw Error(v(301));
        h += 1, or = cn = null, r.updateQueue = null, rt.current = nc, n = o(s, d);
      } while (Ks);
    }
    if (rt.current = tn, r = cn !== null && cn.next !== null, zt = 0, or = cn = Ct = null, ff = !1, r) throw Error(v(300));
    return n;
  }
  function Go() {
    var n = Xs !== 0;
    return Xs = 0, n;
  }
  function mr() {
    var n = { memoizedState: null, baseState: null, baseQueue: null, queue: null, next: null };
    return or === null ? Ct.memoizedState = or = n : or = or.next = n, or;
  }
  function yr() {
    if (cn === null) {
      var n = Ct.alternate;
      n = n !== null ? n.memoizedState : null;
    } else n = cn.next;
    var r = or === null ? Ct.memoizedState : or.next;
    if (r !== null) or = r, cn = n;
    else {
      if (n === null) throw Error(v(310));
      cn = n, n = { memoizedState: cn.memoizedState, baseState: cn.baseState, baseQueue: cn.baseQueue, queue: cn.queue, next: null }, or === null ? Ct.memoizedState = or = n : or = or.next = n;
    }
    return or;
  }
  function ma(n, r) {
    return typeof r == "function" ? r(n) : r;
  }
  function Fl(n) {
    var r = yr(), o = r.queue;
    if (o === null) throw Error(v(311));
    o.lastRenderedReducer = n;
    var s = cn, d = s.baseQueue, h = o.pending;
    if (h !== null) {
      if (d !== null) {
        var b = d.next;
        d.next = h.next, h.next = b;
      }
      s.baseQueue = d = h, o.pending = null;
    }
    if (d !== null) {
      h = d.next, s = s.baseState;
      var O = b = null, P = null, J = h;
      do {
        var ve = J.lane;
        if ((zt & ve) === ve) P !== null && (P = P.next = { lane: 0, action: J.action, hasEagerState: J.hasEagerState, eagerState: J.eagerState, next: null }), s = J.hasEagerState ? J.eagerState : n(s, J.action);
        else {
          var he = {
            lane: ve,
            action: J.action,
            hasEagerState: J.hasEagerState,
            eagerState: J.eagerState,
            next: null
          };
          P === null ? (O = P = he, b = s) : P = P.next = he, Ct.lanes |= ve, Gl |= ve;
        }
        J = J.next;
      } while (J !== null && J !== h);
      P === null ? b = s : P.next = O, yi(s, r.memoizedState) || (gr = !0), r.memoizedState = s, r.baseState = b, r.baseQueue = P, o.lastRenderedState = s;
    }
    if (n = o.interleaved, n !== null) {
      d = n;
      do
        h = d.lane, Ct.lanes |= h, Gl |= h, d = d.next;
      while (d !== n);
    } else d === null && (o.lanes = 0);
    return [r.memoizedState, o.dispatch];
  }
  function Qo(n) {
    var r = yr(), o = r.queue;
    if (o === null) throw Error(v(311));
    o.lastRenderedReducer = n;
    var s = o.dispatch, d = o.pending, h = r.memoizedState;
    if (d !== null) {
      o.pending = null;
      var b = d = d.next;
      do
        h = n(h, b.action), b = b.next;
      while (b !== d);
      yi(h, r.memoizedState) || (gr = !0), r.memoizedState = h, r.baseQueue === null && (r.baseState = h), o.lastRenderedState = h;
    }
    return [h, s];
  }
  function ju() {
  }
  function df(n, r) {
    var o = Ct, s = yr(), d = r(), h = !yi(s.memoizedState, d);
    if (h && (s.memoizedState = d, gr = !0), s = s.queue, Js(hf.bind(null, o, s, n), [n]), s.getSnapshot !== r || h || or !== null && or.memoizedState.tag & 1) {
      if (o.flags |= 2048, jl(9, vf.bind(null, o, s, d, r), void 0, null), tr === null) throw Error(v(349));
      zt & 30 || pf(o, r, d);
    }
    return d;
  }
  function pf(n, r, o) {
    n.flags |= 16384, n = { getSnapshot: r, value: o }, r = Ct.updateQueue, r === null ? (r = { lastEffect: null, stores: null }, Ct.updateQueue = r, r.stores = [n]) : (o = r.stores, o === null ? r.stores = [n] : o.push(n));
  }
  function vf(n, r, o, s) {
    r.value = o, r.getSnapshot = s, mf(r) && yf(n);
  }
  function hf(n, r, o) {
    return o(function() {
      mf(r) && yf(n);
    });
  }
  function mf(n) {
    var r = n.getSnapshot;
    n = n.value;
    try {
      var o = r();
      return !yi(n, o);
    } catch {
      return !0;
    }
  }
  function yf(n) {
    var r = Hi(n, 1);
    r !== null && $a(r, n, 1, -1);
  }
  function gf(n) {
    var r = mr();
    return typeof n == "function" && (n = n()), r.memoizedState = r.baseState = n, n = { pending: null, interleaved: null, lanes: 0, dispatch: null, lastRenderedReducer: ma, lastRenderedState: n }, r.queue = n, n = n.dispatch = tc.bind(null, Ct, n), [r.memoizedState, n];
  }
  function jl(n, r, o, s) {
    return n = { tag: n, create: r, destroy: o, deps: s, next: null }, r = Ct.updateQueue, r === null ? (r = { lastEffect: null, stores: null }, Ct.updateQueue = r, r.lastEffect = n.next = n) : (o = r.lastEffect, o === null ? r.lastEffect = n.next = n : (s = o.next, o.next = n, n.next = s, r.lastEffect = n)), n;
  }
  function Sf() {
    return yr().memoizedState;
  }
  function Hu(n, r, o, s) {
    var d = mr();
    Ct.flags |= n, d.memoizedState = jl(1 | r, o, void 0, s === void 0 ? null : s);
  }
  function Vu(n, r, o, s) {
    var d = yr();
    s = s === void 0 ? null : s;
    var h = void 0;
    if (cn !== null) {
      var b = cn.memoizedState;
      if (h = b.destroy, s !== null && er(s, b.deps)) {
        d.memoizedState = jl(r, o, h, s);
        return;
      }
    }
    Ct.flags |= n, d.memoizedState = jl(1 | r, o, h, s);
  }
  function Ef(n, r) {
    return Hu(8390656, 8, n, r);
  }
  function Js(n, r) {
    return Vu(2048, 8, n, r);
  }
  function Cf(n, r) {
    return Vu(4, 2, n, r);
  }
  function bf(n, r) {
    return Vu(4, 4, n, r);
  }
  function Zs(n, r) {
    if (typeof r == "function") return n = n(), r(n), function() {
      r(null);
    };
    if (r != null) return n = n(), r.current = n, function() {
      r.current = null;
    };
  }
  function Hl(n, r, o) {
    return o = o != null ? o.concat([n]) : null, Vu(4, 4, Zs.bind(null, r, n), o);
  }
  function ec() {
  }
  function Tf(n, r) {
    var o = yr();
    r = r === void 0 ? null : r;
    var s = o.memoizedState;
    return s !== null && r !== null && er(r, s[1]) ? s[0] : (o.memoizedState = [n, r], n);
  }
  function Rf(n, r) {
    var o = yr();
    r = r === void 0 ? null : r;
    var s = o.memoizedState;
    return s !== null && r !== null && er(r, s[1]) ? s[0] : (n = n(), o.memoizedState = [n, r], n);
  }
  function wf(n, r, o) {
    return zt & 21 ? (yi(o, r) || (o = bl(), Ct.lanes |= o, Gl |= o, n.baseState = !0), r) : (n.baseState && (n.baseState = !1, gr = !0), n.memoizedState = o);
  }
  function Ih(n, r) {
    var o = Pt;
    Pt = o !== 0 && 4 > o ? o : 4, n(!0);
    var s = Dt.transition;
    Dt.transition = {};
    try {
      n(!1), r();
    } finally {
      Pt = o, Dt.transition = s;
    }
  }
  function Bu() {
    return yr().memoizedState;
  }
  function Yh(n, r, o) {
    var s = Pa(n);
    if (o = { lane: s, action: o, hasEagerState: !1, eagerState: null, next: null }, qo(n)) La(r, o);
    else if (o = Hh(n, r, o, s), o !== null) {
      var d = yn();
      $a(o, n, s, d), Wh(o, r, s);
    }
  }
  function tc(n, r, o) {
    var s = Pa(n), d = { lane: s, action: o, hasEagerState: !1, eagerState: null, next: null };
    if (qo(n)) La(r, d);
    else {
      var h = n.alternate;
      if (n.lanes === 0 && (h === null || h.lanes === 0) && (h = r.lastRenderedReducer, h !== null)) try {
        var b = r.lastRenderedState, O = h(b, o);
        if (d.hasEagerState = !0, d.eagerState = O, yi(O, b)) {
          var P = r.interleaved;
          P === null ? (d.next = d, vp(r)) : (d.next = P.next, P.next = d), r.interleaved = d;
          return;
        }
      } catch {
      } finally {
      }
      o = Hh(n, r, d, s), o !== null && (d = yn(), $a(o, n, s, d), Wh(o, r, s));
    }
  }
  function qo(n) {
    var r = n.alternate;
    return n === Ct || r !== null && r === Ct;
  }
  function La(n, r) {
    Ks = ff = !0;
    var o = n.pending;
    o === null ? r.next = r : (r.next = o.next, o.next = r), n.pending = r;
  }
  function Wh(n, r, o) {
    if (o & 4194240) {
      var s = r.lanes;
      s &= n.pendingLanes, o |= s, r.lanes = o, Rs(n, o);
    }
  }
  var tn = { readContext: en, useCallback: oe, useContext: oe, useEffect: oe, useImperativeHandle: oe, useInsertionEffect: oe, useLayoutEffect: oe, useMemo: oe, useReducer: oe, useRef: oe, useState: oe, useDebugValue: oe, useDeferredValue: oe, useTransition: oe, useMutableSource: oe, useSyncExternalStore: oe, useId: oe, unstable_isNewReconciler: !1 }, xf = { readContext: en, useCallback: function(n, r) {
    return mr().memoizedState = [n, r === void 0 ? null : r], n;
  }, useContext: en, useEffect: Ef, useImperativeHandle: function(n, r, o) {
    return o = o != null ? o.concat([n]) : null, Hu(
      4194308,
      4,
      Zs.bind(null, r, n),
      o
    );
  }, useLayoutEffect: function(n, r) {
    return Hu(4194308, 4, n, r);
  }, useInsertionEffect: function(n, r) {
    return Hu(4, 2, n, r);
  }, useMemo: function(n, r) {
    var o = mr();
    return r = r === void 0 ? null : r, n = n(), o.memoizedState = [n, r], n;
  }, useReducer: function(n, r, o) {
    var s = mr();
    return r = o !== void 0 ? o(r) : r, s.memoizedState = s.baseState = r, n = { pending: null, interleaved: null, lanes: 0, dispatch: null, lastRenderedReducer: n, lastRenderedState: r }, s.queue = n, n = n.dispatch = Yh.bind(null, Ct, n), [s.memoizedState, n];
  }, useRef: function(n) {
    var r = mr();
    return n = { current: n }, r.memoizedState = n;
  }, useState: gf, useDebugValue: ec, useDeferredValue: function(n) {
    return mr().memoizedState = n;
  }, useTransition: function() {
    var n = gf(!1), r = n[0];
    return n = Ih.bind(null, n[1]), mr().memoizedState = n, [r, n];
  }, useMutableSource: function() {
  }, useSyncExternalStore: function(n, r, o) {
    var s = Ct, d = mr();
    if (xn) {
      if (o === void 0) throw Error(v(407));
      o = o();
    } else {
      if (o = r(), tr === null) throw Error(v(349));
      zt & 30 || pf(s, r, o);
    }
    d.memoizedState = o;
    var h = { value: o, getSnapshot: r };
    return d.queue = h, Ef(hf.bind(
      null,
      s,
      h,
      n
    ), [n]), s.flags |= 2048, jl(9, vf.bind(null, s, h, o, r), void 0, null), o;
  }, useId: function() {
    var n = mr(), r = tr.identifierPrefix;
    if (xn) {
      var o = ji, s = qr;
      o = (s & ~(1 << 32 - Yr(s) - 1)).toString(32) + o, r = ":" + r + "R" + o, o = Xs++, 0 < o && (r += "H" + o.toString(32)), r += ":";
    } else o = Ep++, r = ":" + r + "r" + o.toString(32) + ":";
    return n.memoizedState = r;
  }, unstable_isNewReconciler: !1 }, _f = {
    readContext: en,
    useCallback: Tf,
    useContext: en,
    useEffect: Js,
    useImperativeHandle: Hl,
    useInsertionEffect: Cf,
    useLayoutEffect: bf,
    useMemo: Rf,
    useReducer: Fl,
    useRef: Sf,
    useState: function() {
      return Fl(ma);
    },
    useDebugValue: ec,
    useDeferredValue: function(n) {
      var r = yr();
      return wf(r, cn.memoizedState, n);
    },
    useTransition: function() {
      var n = Fl(ma)[0], r = yr().memoizedState;
      return [n, r];
    },
    useMutableSource: ju,
    useSyncExternalStore: df,
    useId: Bu,
    unstable_isNewReconciler: !1
  }, nc = { readContext: en, useCallback: Tf, useContext: en, useEffect: Js, useImperativeHandle: Hl, useInsertionEffect: Cf, useLayoutEffect: bf, useMemo: Rf, useReducer: Qo, useRef: Sf, useState: function() {
    return Qo(ma);
  }, useDebugValue: ec, useDeferredValue: function(n) {
    var r = yr();
    return cn === null ? r.memoizedState = n : wf(r, cn.memoizedState, n);
  }, useTransition: function() {
    var n = Qo(ma)[0], r = yr().memoizedState;
    return [n, r];
  }, useMutableSource: ju, useSyncExternalStore: df, useId: Bu, unstable_isNewReconciler: !1 };
  function ya(n, r) {
    if (n && n.defaultProps) {
      r = ke({}, r), n = n.defaultProps;
      for (var o in n) r[o] === void 0 && (r[o] = n[o]);
      return r;
    }
    return r;
  }
  function Cp(n, r, o, s) {
    r = n.memoizedState, o = o(s, r), o = o == null ? r : ke({}, r, o), n.memoizedState = o, n.lanes === 0 && (n.updateQueue.baseState = o);
  }
  var kf = { isMounted: function(n) {
    return (n = n._reactInternals) ? Ue(n) === n : !1;
  }, enqueueSetState: function(n, r, o) {
    n = n._reactInternals;
    var s = yn(), d = Pa(n), h = yo(s, d);
    h.payload = r, o != null && (h.callback = o), r = Wo(n, h, d), r !== null && ($a(r, n, d, s), uf(r, n, d));
  }, enqueueReplaceState: function(n, r, o) {
    n = n._reactInternals;
    var s = yn(), d = Pa(n), h = yo(s, d);
    h.tag = 1, h.payload = r, o != null && (h.callback = o), r = Wo(n, h, d), r !== null && ($a(r, n, d, s), uf(r, n, d));
  }, enqueueForceUpdate: function(n, r) {
    n = n._reactInternals;
    var o = yn(), s = Pa(n), d = yo(o, s);
    d.tag = 2, r != null && (d.callback = r), r = Wo(n, d, s), r !== null && ($a(r, n, s, o), uf(r, n, s));
  } };
  function Gh(n, r, o, s, d, h, b) {
    return n = n.stateNode, typeof n.shouldComponentUpdate == "function" ? n.shouldComponentUpdate(s, h, b) : r.prototype && r.prototype.isPureReactComponent ? !Ns(o, s) || !Ns(d, h) : !0;
  }
  function Qh(n, r, o) {
    var s = !1, d = Ot, h = r.contextType;
    return typeof h == "object" && h !== null ? h = en(h) : (d = Jn(r) ? Xa : Un.current, s = r.contextTypes, h = (s = s != null) ? Aa(n, d) : Ot), r = new r(o, h), n.memoizedState = r.state !== null && r.state !== void 0 ? r.state : null, r.updater = kf, n.stateNode = r, r._reactInternals = n, s && (n = n.stateNode, n.__reactInternalMemoizedUnmaskedChildContext = d, n.__reactInternalMemoizedMaskedChildContext = h), r;
  }
  function Of(n, r, o, s) {
    n = r.state, typeof r.componentWillReceiveProps == "function" && r.componentWillReceiveProps(o, s), typeof r.UNSAFE_componentWillReceiveProps == "function" && r.UNSAFE_componentWillReceiveProps(o, s), r.state !== n && kf.enqueueReplaceState(r, r.state, null);
  }
  function bp(n, r, o, s) {
    var d = n.stateNode;
    d.props = o, d.state = n.memoizedState, d.refs = {}, Yo(n);
    var h = r.contextType;
    typeof h == "object" && h !== null ? d.context = en(h) : (h = Jn(r) ? Xa : Un.current, d.context = Aa(n, h)), d.state = n.memoizedState, h = r.getDerivedStateFromProps, typeof h == "function" && (Cp(n, r, h, o), d.state = n.memoizedState), typeof r.getDerivedStateFromProps == "function" || typeof d.getSnapshotBeforeUpdate == "function" || typeof d.UNSAFE_componentWillMount != "function" && typeof d.componentWillMount != "function" || (r = d.state, typeof d.componentWillMount == "function" && d.componentWillMount(), typeof d.UNSAFE_componentWillMount == "function" && d.UNSAFE_componentWillMount(), r !== d.state && kf.enqueueReplaceState(d, d.state, null), sf(n, o, d, s), d.state = n.memoizedState), typeof d.componentDidMount == "function" && (n.flags |= 4194308);
  }
  function Ko(n, r) {
    try {
      var o = "", s = r;
      do
        o += be(s), s = s.return;
      while (s);
      var d = o;
    } catch (h) {
      d = `
Error generating stack: ` + h.message + `
` + h.stack;
    }
    return { value: n, source: r, stack: d, digest: null };
  }
  function Df(n, r, o) {
    return { value: n, source: null, stack: o ?? null, digest: r ?? null };
  }
  function Tp(n, r) {
    try {
      console.error(r.value);
    } catch (o) {
      setTimeout(function() {
        throw o;
      });
    }
  }
  var $g = typeof WeakMap == "function" ? WeakMap : Map;
  function rc(n, r, o) {
    o = yo(-1, o), o.tag = 3, o.payload = { element: null };
    var s = r.value;
    return o.callback = function() {
      Jo || (Jo = !0, fc = s), Tp(n, r);
    }, o;
  }
  function qh(n, r, o) {
    o = yo(-1, o), o.tag = 3;
    var s = n.type.getDerivedStateFromError;
    if (typeof s == "function") {
      var d = r.value;
      o.payload = function() {
        return s(d);
      }, o.callback = function() {
        Tp(n, r);
      };
    }
    var h = n.stateNode;
    return h !== null && typeof h.componentDidCatch == "function" && (o.callback = function() {
      Tp(n, r), typeof s != "function" && (ni === null ? ni = /* @__PURE__ */ new Set([this]) : ni.add(this));
      var b = r.stack;
      this.componentDidCatch(r.value, { componentStack: b !== null ? b : "" });
    }), o;
  }
  function Rp(n, r, o) {
    var s = n.pingCache;
    if (s === null) {
      s = n.pingCache = new $g();
      var d = /* @__PURE__ */ new Set();
      s.set(r, d);
    } else d = s.get(r), d === void 0 && (d = /* @__PURE__ */ new Set(), s.set(r, d));
    d.has(o) || (d.add(o), n = Pp.bind(null, n, r, o), r.then(n, n));
  }
  function wp(n) {
    do {
      var r;
      if ((r = n.tag === 13) && (r = n.memoizedState, r = r !== null ? r.dehydrated !== null : !0), r) return n;
      n = n.return;
    } while (n !== null);
    return null;
  }
  function Kh(n, r, o, s, d) {
    return n.mode & 1 ? (n.flags |= 65536, n.lanes = d, n) : (n === r ? n.flags |= 65536 : (n.flags |= 128, o.flags |= 131072, o.flags &= -52805, o.tag === 1 && (o.alternate === null ? o.tag = 17 : (r = yo(-1, 1), r.tag = 2, Wo(o, r, 1))), o.lanes |= 1), n);
  }
  var Vl = ue.ReactCurrentOwner, gr = !1;
  function Bn(n, r, o, s) {
    r.child = n === null ? wr(r, null, o, s) : Ci(r, n.child, o, s);
  }
  function Nf(n, r, o, s, d) {
    o = o.render;
    var h = r.ref;
    return Pu(r, d), s = ct(n, r, o, s, h, d), o = Go(), n !== null && !gr ? (r.updateQueue = n.updateQueue, r.flags &= -2053, n.lanes &= ~d, xr(n, r, d)) : (xn && o && ip(r), r.flags |= 1, Bn(n, r, s, d), r.child);
  }
  function ga(n, r, o, s, d) {
    if (n === null) {
      var h = o.type;
      return typeof h == "function" && !Fp(h) && h.defaultProps === void 0 && o.compare === null && o.defaultProps === void 0 ? (r.tag = 15, r.type = h, Bl(n, r, h, s, d)) : (n = Wf(o.type, null, s, r, r.mode, d), n.ref = r.ref, n.return = r, r.child = n);
    }
    if (h = n.child, !(n.lanes & d)) {
      var b = h.memoizedProps;
      if (o = o.compare, o = o !== null ? o : Ns, o(b, s) && n.ref === r.ref) return xr(n, r, d);
    }
    return r.flags |= 1, n = tl(h, s), n.ref = r.ref, n.return = r, r.child = n;
  }
  function Bl(n, r, o, s, d) {
    if (n !== null) {
      var h = n.memoizedProps;
      if (Ns(h, s) && n.ref === r.ref) if (gr = !1, r.pendingProps = s = h, (n.lanes & d) !== 0) n.flags & 131072 && (gr = !0);
      else return r.lanes = n.lanes, xr(n, r, d);
    }
    return Af(n, r, o, s, d);
  }
  function Tt(n, r, o) {
    var s = r.pendingProps, d = s.children, h = n !== null ? n.memoizedState : null;
    if (s.mode === "hidden") if (!(r.mode & 1)) r.memoizedState = { baseLanes: 0, cachePool: null, transitions: null }, mn(Gu, Ua), Ua |= o;
    else {
      if (!(o & 1073741824)) return n = h !== null ? h.baseLanes | o : o, r.lanes = r.childLanes = 1073741824, r.memoizedState = { baseLanes: n, cachePool: null, transitions: null }, r.updateQueue = null, mn(Gu, Ua), Ua |= n, null;
      r.memoizedState = { baseLanes: 0, cachePool: null, transitions: null }, s = h !== null ? h.baseLanes : o, mn(Gu, Ua), Ua |= s;
    }
    else h !== null ? (s = h.baseLanes | o, r.memoizedState = null) : s = o, mn(Gu, Ua), Ua |= s;
    return Bn(n, r, d, o), r.child;
  }
  function ac(n, r) {
    var o = r.ref;
    (n === null && o !== null || n !== null && n.ref !== o) && (r.flags |= 512, r.flags |= 2097152);
  }
  function Af(n, r, o, s, d) {
    var h = Jn(o) ? Xa : Un.current;
    return h = Aa(r, h), Pu(r, d), o = ct(n, r, o, s, h, d), s = Go(), n !== null && !gr ? (r.updateQueue = n.updateQueue, r.flags &= -2053, n.lanes &= ~d, xr(n, r, d)) : (xn && s && ip(r), r.flags |= 1, Bn(n, r, o, d), r.child);
  }
  function Fg(n, r, o, s, d) {
    if (Jn(o)) {
      var h = !0;
      Ll(r);
    } else h = !1;
    if (Pu(r, d), r.stateNode === null) ei(n, r), Qh(r, o, s), bp(r, o, s, d), s = !0;
    else if (n === null) {
      var b = r.stateNode, O = r.memoizedProps;
      b.props = O;
      var P = b.context, J = o.contextType;
      typeof J == "object" && J !== null ? J = en(J) : (J = Jn(o) ? Xa : Un.current, J = Aa(r, J));
      var ve = o.getDerivedStateFromProps, he = typeof ve == "function" || typeof b.getSnapshotBeforeUpdate == "function";
      he || typeof b.UNSAFE_componentWillReceiveProps != "function" && typeof b.componentWillReceiveProps != "function" || (O !== s || P !== J) && Of(r, b, s, J), Za = !1;
      var pe = r.memoizedState;
      b.state = pe, sf(r, s, b, d), P = r.memoizedState, O !== s || pe !== P || Xn.current || Za ? (typeof ve == "function" && (Cp(r, o, ve, s), P = r.memoizedState), (O = Za || Gh(r, o, O, s, pe, P, J)) ? (he || typeof b.UNSAFE_componentWillMount != "function" && typeof b.componentWillMount != "function" || (typeof b.componentWillMount == "function" && b.componentWillMount(), typeof b.UNSAFE_componentWillMount == "function" && b.UNSAFE_componentWillMount()), typeof b.componentDidMount == "function" && (r.flags |= 4194308)) : (typeof b.componentDidMount == "function" && (r.flags |= 4194308), r.memoizedProps = s, r.memoizedState = P), b.props = s, b.state = P, b.context = J, s = O) : (typeof b.componentDidMount == "function" && (r.flags |= 4194308), s = !1);
    } else {
      b = r.stateNode, Vh(n, r), O = r.memoizedProps, J = r.type === r.elementType ? O : ya(r.type, O), b.props = J, he = r.pendingProps, pe = b.context, P = o.contextType, typeof P == "object" && P !== null ? P = en(P) : (P = Jn(o) ? Xa : Un.current, P = Aa(r, P));
      var Ve = o.getDerivedStateFromProps;
      (ve = typeof Ve == "function" || typeof b.getSnapshotBeforeUpdate == "function") || typeof b.UNSAFE_componentWillReceiveProps != "function" && typeof b.componentWillReceiveProps != "function" || (O !== he || pe !== P) && Of(r, b, s, P), Za = !1, pe = r.memoizedState, b.state = pe, sf(r, s, b, d);
      var Xe = r.memoizedState;
      O !== he || pe !== Xe || Xn.current || Za ? (typeof Ve == "function" && (Cp(r, o, Ve, s), Xe = r.memoizedState), (J = Za || Gh(r, o, J, s, pe, Xe, P) || !1) ? (ve || typeof b.UNSAFE_componentWillUpdate != "function" && typeof b.componentWillUpdate != "function" || (typeof b.componentWillUpdate == "function" && b.componentWillUpdate(s, Xe, P), typeof b.UNSAFE_componentWillUpdate == "function" && b.UNSAFE_componentWillUpdate(s, Xe, P)), typeof b.componentDidUpdate == "function" && (r.flags |= 4), typeof b.getSnapshotBeforeUpdate == "function" && (r.flags |= 1024)) : (typeof b.componentDidUpdate != "function" || O === n.memoizedProps && pe === n.memoizedState || (r.flags |= 4), typeof b.getSnapshotBeforeUpdate != "function" || O === n.memoizedProps && pe === n.memoizedState || (r.flags |= 1024), r.memoizedProps = s, r.memoizedState = Xe), b.props = s, b.state = Xe, b.context = P, s = J) : (typeof b.componentDidUpdate != "function" || O === n.memoizedProps && pe === n.memoizedState || (r.flags |= 4), typeof b.getSnapshotBeforeUpdate != "function" || O === n.memoizedProps && pe === n.memoizedState || (r.flags |= 1024), s = !1);
    }
    return xp(n, r, o, s, h, d);
  }
  function xp(n, r, o, s, d, h) {
    ac(n, r);
    var b = (r.flags & 128) !== 0;
    if (!s && !b) return d && Ja(r, o, !1), xr(n, r, h);
    s = r.stateNode, Vl.current = r;
    var O = b && typeof o.getDerivedStateFromError != "function" ? null : s.render();
    return r.flags |= 1, n !== null && b ? (r.child = Ci(r, n.child, null, h), r.child = Ci(r, null, O, h)) : Bn(n, r, O, h), r.memoizedState = s.state, d && Ja(r, o, !0), r.child;
  }
  function Mf(n) {
    var r = n.stateNode;
    r.pendingContext ? of(n, r.pendingContext, r.pendingContext !== r.context) : r.context && of(n, r.context, !1), mp(n, r.containerInfo);
  }
  function Iu(n, r, o, s, d) {
    return mo(), Ys(d), r.flags |= 256, Bn(n, r, o, s), r.child;
  }
  var _p = { dehydrated: null, treeContext: null, retryLane: 0 };
  function Lf(n) {
    return { baseLanes: n, cachePool: null, transitions: null };
  }
  function Xh(n, r, o) {
    var s = r.pendingProps, d = Nn.current, h = !1, b = (r.flags & 128) !== 0, O;
    if ((O = b) || (O = n !== null && n.memoizedState === null ? !1 : (d & 2) !== 0), O ? (h = !0, r.flags &= -129) : (n === null || n.memoizedState !== null) && (d |= 1), mn(Nn, d & 1), n === null)
      return sp(r), n = r.memoizedState, n !== null && (n = n.dehydrated, n !== null) ? (r.mode & 1 ? n.data === "$!" ? r.lanes = 8 : r.lanes = 1073741824 : r.lanes = 1, null) : (b = s.children, n = s.fallback, h ? (s = r.mode, h = r.child, b = { mode: "hidden", children: b }, !(s & 1) && h !== null ? (h.childLanes = 0, h.pendingProps = b) : h = Zu(b, s, 0, null), n = nl(n, s, o, null), h.return = r, n.return = r, h.sibling = n, r.child = h, r.child.memoizedState = Lf(o), r.memoizedState = _p, n) : ic(r, b));
    if (d = n.memoizedState, d !== null && (O = d.dehydrated, O !== null)) return Jh(n, r, b, s, O, d, o);
    if (h) {
      h = s.fallback, b = r.mode, d = n.child, O = d.sibling;
      var P = { mode: "hidden", children: s.children };
      return !(b & 1) && r.child !== d ? (s = r.child, s.childLanes = 0, s.pendingProps = P, r.deletions = null) : (s = tl(d, P), s.subtreeFlags = d.subtreeFlags & 14680064), O !== null ? h = tl(O, h) : (h = nl(h, b, o, null), h.flags |= 2), h.return = r, s.return = r, s.sibling = h, r.child = s, s = h, h = r.child, b = n.child.memoizedState, b = b === null ? Lf(o) : { baseLanes: b.baseLanes | o, cachePool: null, transitions: b.transitions }, h.memoizedState = b, h.childLanes = n.childLanes & ~o, r.memoizedState = _p, s;
    }
    return h = n.child, n = h.sibling, s = tl(h, { mode: "visible", children: s.children }), !(r.mode & 1) && (s.lanes = o), s.return = r, s.sibling = null, n !== null && (o = r.deletions, o === null ? (r.deletions = [n], r.flags |= 16) : o.push(n)), r.child = s, r.memoizedState = null, s;
  }
  function ic(n, r) {
    return r = Zu({ mode: "visible", children: r }, n.mode, 0, null), r.return = n, n.child = r;
  }
  function zf(n, r, o, s) {
    return s !== null && Ys(s), Ci(r, n.child, null, o), n = ic(r, r.pendingProps.children), n.flags |= 2, r.memoizedState = null, n;
  }
  function Jh(n, r, o, s, d, h, b) {
    if (o)
      return r.flags & 256 ? (r.flags &= -257, s = Df(Error(v(422))), zf(n, r, b, s)) : r.memoizedState !== null ? (r.child = n.child, r.flags |= 128, null) : (h = s.fallback, d = r.mode, s = Zu({ mode: "visible", children: s.children }, d, 0, null), h = nl(h, d, b, null), h.flags |= 2, s.return = r, h.return = r, s.sibling = h, r.child = s, r.mode & 1 && Ci(r, n.child, null, b), r.child.memoizedState = Lf(b), r.memoizedState = _p, h);
    if (!(r.mode & 1)) return zf(n, r, b, null);
    if (d.data === "$!") {
      if (s = d.nextSibling && d.nextSibling.dataset, s) var O = s.dgst;
      return s = O, h = Error(v(419)), s = Df(h, s, void 0), zf(n, r, b, s);
    }
    if (O = (b & n.childLanes) !== 0, gr || O) {
      if (s = tr, s !== null) {
        switch (b & -b) {
          case 4:
            d = 2;
            break;
          case 16:
            d = 8;
            break;
          case 64:
          case 128:
          case 256:
          case 512:
          case 1024:
          case 2048:
          case 4096:
          case 8192:
          case 16384:
          case 32768:
          case 65536:
          case 131072:
          case 262144:
          case 524288:
          case 1048576:
          case 2097152:
          case 4194304:
          case 8388608:
          case 16777216:
          case 33554432:
          case 67108864:
            d = 32;
            break;
          case 536870912:
            d = 268435456;
            break;
          default:
            d = 0;
        }
        d = d & (s.suspendedLanes | b) ? 0 : d, d !== 0 && d !== h.retryLane && (h.retryLane = d, Hi(n, d), $a(s, n, d, -1));
      }
      return zp(), s = Df(Error(v(421))), zf(n, r, b, s);
    }
    return d.data === "$?" ? (r.flags |= 128, r.child = n.child, r = Yg.bind(null, n), d._reactRetry = r, null) : (n = h.treeContext, ha = gi(d.nextSibling), va = r, xn = !0, Ei = null, n !== null && (Rr[Zn++] = qr, Rr[Zn++] = ji, Rr[Zn++] = zl, qr = n.id, ji = n.overflow, zl = r), r = ic(r, s.children), r.flags |= 4096, r);
  }
  function kp(n, r, o) {
    n.lanes |= r;
    var s = n.alternate;
    s !== null && (s.lanes |= r), pp(n.return, r, o);
  }
  function Uf(n, r, o, s, d) {
    var h = n.memoizedState;
    h === null ? n.memoizedState = { isBackwards: r, rendering: null, renderingStartTime: 0, last: s, tail: o, tailMode: d } : (h.isBackwards = r, h.rendering = null, h.renderingStartTime = 0, h.last = s, h.tail = o, h.tailMode = d);
  }
  function Sa(n, r, o) {
    var s = r.pendingProps, d = s.revealOrder, h = s.tail;
    if (Bn(n, r, s.children, o), s = Nn.current, s & 2) s = s & 1 | 2, r.flags |= 128;
    else {
      if (n !== null && n.flags & 128) e: for (n = r.child; n !== null; ) {
        if (n.tag === 13) n.memoizedState !== null && kp(n, o, r);
        else if (n.tag === 19) kp(n, o, r);
        else if (n.child !== null) {
          n.child.return = n, n = n.child;
          continue;
        }
        if (n === r) break e;
        for (; n.sibling === null; ) {
          if (n.return === null || n.return === r) break e;
          n = n.return;
        }
        n.sibling.return = n.return, n = n.sibling;
      }
      s &= 1;
    }
    if (mn(Nn, s), !(r.mode & 1)) r.memoizedState = null;
    else switch (d) {
      case "forwards":
        for (o = r.child, d = null; o !== null; ) n = o.alternate, n !== null && cf(n) === null && (d = o), o = o.sibling;
        o = d, o === null ? (d = r.child, r.child = null) : (d = o.sibling, o.sibling = null), Uf(r, !1, d, o, h);
        break;
      case "backwards":
        for (o = null, d = r.child, r.child = null; d !== null; ) {
          if (n = d.alternate, n !== null && cf(n) === null) {
            r.child = d;
            break;
          }
          n = d.sibling, d.sibling = o, o = d, d = n;
        }
        Uf(r, !0, o, null, h);
        break;
      case "together":
        Uf(r, !1, null, null, void 0);
        break;
      default:
        r.memoizedState = null;
    }
    return r.child;
  }
  function ei(n, r) {
    !(r.mode & 1) && n !== null && (n.alternate = null, r.alternate = null, r.flags |= 2);
  }
  function xr(n, r, o) {
    if (n !== null && (r.dependencies = n.dependencies), Gl |= r.lanes, !(o & r.childLanes)) return null;
    if (n !== null && r.child !== n.child) throw Error(v(153));
    if (r.child !== null) {
      for (n = r.child, o = tl(n, n.pendingProps), r.child = o, o.return = r; n.sibling !== null; ) n = n.sibling, o = o.sibling = tl(n, n.pendingProps), o.return = r;
      o.sibling = null;
    }
    return r.child;
  }
  function Pf(n, r, o) {
    switch (r.tag) {
      case 3:
        Mf(r), mo();
        break;
      case 5:
        yp(r);
        break;
      case 1:
        Jn(r.type) && Ll(r);
        break;
      case 4:
        mp(r, r.stateNode.containerInfo);
        break;
      case 10:
        var s = r.type._context, d = r.memoizedProps.value;
        mn(Ne, s._currentValue), s._currentValue = d;
        break;
      case 13:
        if (s = r.memoizedState, s !== null)
          return s.dehydrated !== null ? (mn(Nn, Nn.current & 1), r.flags |= 128, null) : o & r.child.childLanes ? Xh(n, r, o) : (mn(Nn, Nn.current & 1), n = xr(n, r, o), n !== null ? n.sibling : null);
        mn(Nn, Nn.current & 1);
        break;
      case 19:
        if (s = (o & r.childLanes) !== 0, n.flags & 128) {
          if (s) return Sa(n, r, o);
          r.flags |= 128;
        }
        if (d = r.memoizedState, d !== null && (d.rendering = null, d.tail = null, d.lastEffect = null), mn(Nn, Nn.current), s) break;
        return null;
      case 22:
      case 23:
        return r.lanes = 0, Tt(n, r, o);
    }
    return xr(n, r, o);
  }
  var Yu, za, lr, Zh;
  Yu = function(n, r) {
    for (var o = r.child; o !== null; ) {
      if (o.tag === 5 || o.tag === 6) n.appendChild(o.stateNode);
      else if (o.tag !== 4 && o.child !== null) {
        o.child.return = o, o = o.child;
        continue;
      }
      if (o === r) break;
      for (; o.sibling === null; ) {
        if (o.return === null || o.return === r) return;
        o = o.return;
      }
      o.sibling.return = o.return, o = o.sibling;
    }
  }, za = function() {
  }, lr = function(n, r, o, s) {
    var d = n.memoizedProps;
    if (d !== s) {
      n = r.stateNode, $l(Vi.current);
      var h = null;
      switch (o) {
        case "input":
          d = Wt(n, d), s = Wt(n, s), h = [];
          break;
        case "select":
          d = ke({}, d, { value: void 0 }), s = ke({}, s, { value: void 0 }), h = [];
          break;
        case "textarea":
          d = dr(n, d), s = dr(n, s), h = [];
          break;
        default:
          typeof d.onClick != "function" && typeof s.onClick == "function" && (n.onclick = tf);
      }
      Tn(o, s);
      var b;
      o = null;
      for (J in d) if (!s.hasOwnProperty(J) && d.hasOwnProperty(J) && d[J] != null) if (J === "style") {
        var O = d[J];
        for (b in O) O.hasOwnProperty(b) && (o || (o = {}), o[b] = "");
      } else J !== "dangerouslySetInnerHTML" && J !== "children" && J !== "suppressContentEditableWarning" && J !== "suppressHydrationWarning" && J !== "autoFocus" && (S.hasOwnProperty(J) ? h || (h = []) : (h = h || []).push(J, null));
      for (J in s) {
        var P = s[J];
        if (O = d != null ? d[J] : void 0, s.hasOwnProperty(J) && P !== O && (P != null || O != null)) if (J === "style") if (O) {
          for (b in O) !O.hasOwnProperty(b) || P && P.hasOwnProperty(b) || (o || (o = {}), o[b] = "");
          for (b in P) P.hasOwnProperty(b) && O[b] !== P[b] && (o || (o = {}), o[b] = P[b]);
        } else o || (h || (h = []), h.push(
          J,
          o
        )), o = P;
        else J === "dangerouslySetInnerHTML" ? (P = P ? P.__html : void 0, O = O ? O.__html : void 0, P != null && O !== P && (h = h || []).push(J, P)) : J === "children" ? typeof P != "string" && typeof P != "number" || (h = h || []).push(J, "" + P) : J !== "suppressContentEditableWarning" && J !== "suppressHydrationWarning" && (S.hasOwnProperty(J) ? (P != null && J === "onScroll" && Xt("scroll", n), h || O === P || (h = [])) : (h = h || []).push(J, P));
      }
      o && (h = h || []).push("style", o);
      var J = h;
      (r.updateQueue = J) && (r.flags |= 4);
    }
  }, Zh = function(n, r, o, s) {
    o !== s && (r.flags |= 4);
  };
  function oc(n, r) {
    if (!xn) switch (n.tailMode) {
      case "hidden":
        r = n.tail;
        for (var o = null; r !== null; ) r.alternate !== null && (o = r), r = r.sibling;
        o === null ? n.tail = null : o.sibling = null;
        break;
      case "collapsed":
        o = n.tail;
        for (var s = null; o !== null; ) o.alternate !== null && (s = o), o = o.sibling;
        s === null ? r || n.tail === null ? n.tail = null : n.tail.sibling = null : s.sibling = null;
    }
  }
  function Vr(n) {
    var r = n.alternate !== null && n.alternate.child === n.child, o = 0, s = 0;
    if (r) for (var d = n.child; d !== null; ) o |= d.lanes | d.childLanes, s |= d.subtreeFlags & 14680064, s |= d.flags & 14680064, d.return = n, d = d.sibling;
    else for (d = n.child; d !== null; ) o |= d.lanes | d.childLanes, s |= d.subtreeFlags, s |= d.flags, d.return = n, d = d.sibling;
    return n.subtreeFlags |= s, n.childLanes = o, r;
  }
  function Op(n, r, o) {
    var s = r.pendingProps;
    switch (lf(r), r.tag) {
      case 2:
      case 16:
      case 15:
      case 0:
      case 11:
      case 7:
      case 8:
      case 12:
      case 9:
      case 14:
        return Vr(r), null;
      case 1:
        return Jn(r.type) && Fi(), Vr(r), null;
      case 3:
        return s = r.stateNode, Fu(), sn(Xn), sn(Un), qs(), s.pendingContext && (s.context = s.pendingContext, s.pendingContext = null), (n === null || n.child === null) && (Vn(r) ? r.flags |= 4 : n === null || n.memoizedState.isDehydrated && !(r.flags & 256) || (r.flags |= 1024, Ei !== null && (hc(Ei), Ei = null))), za(n, r), Vr(r), null;
      case 5:
        gp(r);
        var d = $l(Qs.current);
        if (o = r.type, n !== null && r.stateNode != null) lr(n, r, o, s, d), n.ref !== r.ref && (r.flags |= 512, r.flags |= 2097152);
        else {
          if (!s) {
            if (r.stateNode === null) throw Error(v(166));
            return Vr(r), null;
          }
          if (n = $l(Vi.current), Vn(r)) {
            s = r.stateNode, o = r.type;
            var h = r.memoizedProps;
            switch (s[Ka] = r, s[Hs] = h, n = (r.mode & 1) !== 0, o) {
              case "dialog":
                Xt("cancel", s), Xt("close", s);
                break;
              case "iframe":
              case "object":
              case "embed":
                Xt("load", s);
                break;
              case "video":
              case "audio":
                for (d = 0; d < Us.length; d++) Xt(Us[d], s);
                break;
              case "source":
                Xt("error", s);
                break;
              case "img":
              case "image":
              case "link":
                Xt(
                  "error",
                  s
                ), Xt("load", s);
                break;
              case "details":
                Xt("toggle", s);
                break;
              case "input":
                Fn(s, h), Xt("invalid", s);
                break;
              case "select":
                s._wrapperState = { wasMultiple: !!h.multiple }, Xt("invalid", s);
                break;
              case "textarea":
                pr(s, h), Xt("invalid", s);
            }
            Tn(o, h), d = null;
            for (var b in h) if (h.hasOwnProperty(b)) {
              var O = h[b];
              b === "children" ? typeof O == "string" ? s.textContent !== O && (h.suppressHydrationWarning !== !0 && ef(s.textContent, O, n), d = ["children", O]) : typeof O == "number" && s.textContent !== "" + O && (h.suppressHydrationWarning !== !0 && ef(
                s.textContent,
                O,
                n
              ), d = ["children", "" + O]) : S.hasOwnProperty(b) && O != null && b === "onScroll" && Xt("scroll", s);
            }
            switch (o) {
              case "input":
                ut(s), _a(s, h, !0);
                break;
              case "textarea":
                ut(s), pi(s);
                break;
              case "select":
              case "option":
                break;
              default:
                typeof h.onClick == "function" && (s.onclick = tf);
            }
            s = d, r.updateQueue = s, s !== null && (r.flags |= 4);
          } else {
            b = d.nodeType === 9 ? d : d.ownerDocument, n === "http://www.w3.org/1999/xhtml" && (n = Qn(o)), n === "http://www.w3.org/1999/xhtml" ? o === "script" ? (n = b.createElement("div"), n.innerHTML = "<script><\/script>", n = n.removeChild(n.firstChild)) : typeof s.is == "string" ? n = b.createElement(o, { is: s.is }) : (n = b.createElement(o), o === "select" && (b = n, s.multiple ? b.multiple = !0 : s.size && (b.size = s.size))) : n = b.createElementNS(n, o), n[Ka] = r, n[Hs] = s, Yu(n, r, !1, !1), r.stateNode = n;
            e: {
              switch (b = Rn(o, s), o) {
                case "dialog":
                  Xt("cancel", n), Xt("close", n), d = s;
                  break;
                case "iframe":
                case "object":
                case "embed":
                  Xt("load", n), d = s;
                  break;
                case "video":
                case "audio":
                  for (d = 0; d < Us.length; d++) Xt(Us[d], n);
                  d = s;
                  break;
                case "source":
                  Xt("error", n), d = s;
                  break;
                case "img":
                case "image":
                case "link":
                  Xt(
                    "error",
                    n
                  ), Xt("load", n), d = s;
                  break;
                case "details":
                  Xt("toggle", n), d = s;
                  break;
                case "input":
                  Fn(n, s), d = Wt(n, s), Xt("invalid", n);
                  break;
                case "option":
                  d = s;
                  break;
                case "select":
                  n._wrapperState = { wasMultiple: !!s.multiple }, d = ke({}, s, { value: void 0 }), Xt("invalid", n);
                  break;
                case "textarea":
                  pr(n, s), d = dr(n, s), Xt("invalid", n);
                  break;
                default:
                  d = s;
              }
              Tn(o, d), O = d;
              for (h in O) if (O.hasOwnProperty(h)) {
                var P = O[h];
                h === "style" ? Gt(n, P) : h === "dangerouslySetInnerHTML" ? (P = P ? P.__html : void 0, P != null && eo(n, P)) : h === "children" ? typeof P == "string" ? (o !== "textarea" || P !== "") && ka(n, P) : typeof P == "number" && ka(n, "" + P) : h !== "suppressContentEditableWarning" && h !== "suppressHydrationWarning" && h !== "autoFocus" && (S.hasOwnProperty(h) ? P != null && h === "onScroll" && Xt("scroll", n) : P != null && de(n, h, P, b));
              }
              switch (o) {
                case "input":
                  ut(n), _a(n, s, !1);
                  break;
                case "textarea":
                  ut(n), pi(n);
                  break;
                case "option":
                  s.value != null && n.setAttribute("value", "" + we(s.value));
                  break;
                case "select":
                  n.multiple = !!s.multiple, h = s.value, h != null ? ir(n, !!s.multiple, h, !1) : s.defaultValue != null && ir(
                    n,
                    !!s.multiple,
                    s.defaultValue,
                    !0
                  );
                  break;
                default:
                  typeof d.onClick == "function" && (n.onclick = tf);
              }
              switch (o) {
                case "button":
                case "input":
                case "select":
                case "textarea":
                  s = !!s.autoFocus;
                  break e;
                case "img":
                  s = !0;
                  break e;
                default:
                  s = !1;
              }
            }
            s && (r.flags |= 4);
          }
          r.ref !== null && (r.flags |= 512, r.flags |= 2097152);
        }
        return Vr(r), null;
      case 6:
        if (n && r.stateNode != null) Zh(n, r, n.memoizedProps, s);
        else {
          if (typeof s != "string" && r.stateNode === null) throw Error(v(166));
          if (o = $l(Qs.current), $l(Vi.current), Vn(r)) {
            if (s = r.stateNode, o = r.memoizedProps, s[Ka] = r, (h = s.nodeValue !== o) && (n = va, n !== null)) switch (n.tag) {
              case 3:
                ef(s.nodeValue, o, (n.mode & 1) !== 0);
                break;
              case 5:
                n.memoizedProps.suppressHydrationWarning !== !0 && ef(s.nodeValue, o, (n.mode & 1) !== 0);
            }
            h && (r.flags |= 4);
          } else s = (o.nodeType === 9 ? o : o.ownerDocument).createTextNode(s), s[Ka] = r, r.stateNode = s;
        }
        return Vr(r), null;
      case 13:
        if (sn(Nn), s = r.memoizedState, n === null || n.memoizedState !== null && n.memoizedState.dehydrated !== null) {
          if (xn && ha !== null && r.mode & 1 && !(r.flags & 128)) $h(), mo(), r.flags |= 98560, h = !1;
          else if (h = Vn(r), s !== null && s.dehydrated !== null) {
            if (n === null) {
              if (!h) throw Error(v(318));
              if (h = r.memoizedState, h = h !== null ? h.dehydrated : null, !h) throw Error(v(317));
              h[Ka] = r;
            } else mo(), !(r.flags & 128) && (r.memoizedState = null), r.flags |= 4;
            Vr(r), h = !1;
          } else Ei !== null && (hc(Ei), Ei = null), h = !0;
          if (!h) return r.flags & 65536 ? r : null;
        }
        return r.flags & 128 ? (r.lanes = o, r) : (s = s !== null, s !== (n !== null && n.memoizedState !== null) && s && (r.child.flags |= 8192, r.mode & 1 && (n === null || Nn.current & 1 ? ur === 0 && (ur = 3) : zp())), r.updateQueue !== null && (r.flags |= 4), Vr(r), null);
      case 4:
        return Fu(), za(n, r), n === null && $s(r.stateNode.containerInfo), Vr(r), null;
      case 10:
        return dp(r.type._context), Vr(r), null;
      case 17:
        return Jn(r.type) && Fi(), Vr(r), null;
      case 19:
        if (sn(Nn), h = r.memoizedState, h === null) return Vr(r), null;
        if (s = (r.flags & 128) !== 0, b = h.rendering, b === null) if (s) oc(h, !1);
        else {
          if (ur !== 0 || n !== null && n.flags & 128) for (n = r.child; n !== null; ) {
            if (b = cf(n), b !== null) {
              for (r.flags |= 128, oc(h, !1), s = b.updateQueue, s !== null && (r.updateQueue = s, r.flags |= 4), r.subtreeFlags = 0, s = o, o = r.child; o !== null; ) h = o, n = s, h.flags &= 14680066, b = h.alternate, b === null ? (h.childLanes = 0, h.lanes = n, h.child = null, h.subtreeFlags = 0, h.memoizedProps = null, h.memoizedState = null, h.updateQueue = null, h.dependencies = null, h.stateNode = null) : (h.childLanes = b.childLanes, h.lanes = b.lanes, h.child = b.child, h.subtreeFlags = 0, h.deletions = null, h.memoizedProps = b.memoizedProps, h.memoizedState = b.memoizedState, h.updateQueue = b.updateQueue, h.type = b.type, n = b.dependencies, h.dependencies = n === null ? null : { lanes: n.lanes, firstContext: n.firstContext }), o = o.sibling;
              return mn(Nn, Nn.current & 1 | 2), r.child;
            }
            n = n.sibling;
          }
          h.tail !== null && qt() > qu && (r.flags |= 128, s = !0, oc(h, !1), r.lanes = 4194304);
        }
        else {
          if (!s) if (n = cf(b), n !== null) {
            if (r.flags |= 128, s = !0, o = n.updateQueue, o !== null && (r.updateQueue = o, r.flags |= 4), oc(h, !0), h.tail === null && h.tailMode === "hidden" && !b.alternate && !xn) return Vr(r), null;
          } else 2 * qt() - h.renderingStartTime > qu && o !== 1073741824 && (r.flags |= 128, s = !0, oc(h, !1), r.lanes = 4194304);
          h.isBackwards ? (b.sibling = r.child, r.child = b) : (o = h.last, o !== null ? o.sibling = b : r.child = b, h.last = b);
        }
        return h.tail !== null ? (r = h.tail, h.rendering = r, h.tail = r.sibling, h.renderingStartTime = qt(), r.sibling = null, o = Nn.current, mn(Nn, s ? o & 1 | 2 : o & 1), r) : (Vr(r), null);
      case 22:
      case 23:
        return Lp(), s = r.memoizedState !== null, n !== null && n.memoizedState !== null !== s && (r.flags |= 8192), s && r.mode & 1 ? Ua & 1073741824 && (Vr(r), r.subtreeFlags & 6 && (r.flags |= 8192)) : Vr(r), null;
      case 24:
        return null;
      case 25:
        return null;
    }
    throw Error(v(156, r.tag));
  }
  function em(n, r) {
    switch (lf(r), r.tag) {
      case 1:
        return Jn(r.type) && Fi(), n = r.flags, n & 65536 ? (r.flags = n & -65537 | 128, r) : null;
      case 3:
        return Fu(), sn(Xn), sn(Un), qs(), n = r.flags, n & 65536 && !(n & 128) ? (r.flags = n & -65537 | 128, r) : null;
      case 5:
        return gp(r), null;
      case 13:
        if (sn(Nn), n = r.memoizedState, n !== null && n.dehydrated !== null) {
          if (r.alternate === null) throw Error(v(340));
          mo();
        }
        return n = r.flags, n & 65536 ? (r.flags = n & -65537 | 128, r) : null;
      case 19:
        return sn(Nn), null;
      case 4:
        return Fu(), null;
      case 10:
        return dp(r.type._context), null;
      case 22:
      case 23:
        return Lp(), null;
      case 24:
        return null;
      default:
        return null;
    }
  }
  var Il = !1, _r = !1, jg = typeof WeakSet == "function" ? WeakSet : Set, qe = null;
  function Xo(n, r) {
    var o = n.ref;
    if (o !== null) if (typeof o == "function") try {
      o(null);
    } catch (s) {
      Pn(n, r, s);
    }
    else o.current = null;
  }
  function Dp(n, r, o) {
    try {
      o();
    } catch (s) {
      Pn(n, r, s);
    }
  }
  var Np = !1;
  function Hg(n, r) {
    if (Nl = zo, n = $o(), xu(n)) {
      if ("selectionStart" in n) var o = { start: n.selectionStart, end: n.selectionEnd };
      else e: {
        o = (o = n.ownerDocument) && o.defaultView || window;
        var s = o.getSelection && o.getSelection();
        if (s && s.rangeCount !== 0) {
          o = s.anchorNode;
          var d = s.anchorOffset, h = s.focusNode;
          s = s.focusOffset;
          try {
            o.nodeType, h.nodeType;
          } catch {
            o = null;
            break e;
          }
          var b = 0, O = -1, P = -1, J = 0, ve = 0, he = n, pe = null;
          t: for (; ; ) {
            for (var Ve; he !== o || d !== 0 && he.nodeType !== 3 || (O = b + d), he !== h || s !== 0 && he.nodeType !== 3 || (P = b + s), he.nodeType === 3 && (b += he.nodeValue.length), (Ve = he.firstChild) !== null; )
              pe = he, he = Ve;
            for (; ; ) {
              if (he === n) break t;
              if (pe === o && ++J === d && (O = b), pe === h && ++ve === s && (P = b), (Ve = he.nextSibling) !== null) break;
              he = pe, pe = he.parentNode;
            }
            he = Ve;
          }
          o = O === -1 || P === -1 ? null : { start: O, end: P };
        } else o = null;
      }
      o = o || { start: 0, end: 0 };
    } else o = null;
    for (js = { focusedElem: n, selectionRange: o }, zo = !1, qe = r; qe !== null; ) if (r = qe, n = r.child, (r.subtreeFlags & 1028) !== 0 && n !== null) n.return = r, qe = n;
    else for (; qe !== null; ) {
      r = qe;
      try {
        var Xe = r.alternate;
        if (r.flags & 1024) switch (r.tag) {
          case 0:
          case 11:
          case 15:
            break;
          case 1:
            if (Xe !== null) {
              var Ze = Xe.memoizedProps, Yn = Xe.memoizedState, Y = r.stateNode, H = Y.getSnapshotBeforeUpdate(r.elementType === r.type ? Ze : ya(r.type, Ze), Yn);
              Y.__reactInternalSnapshotBeforeUpdate = H;
            }
            break;
          case 3:
            var Q = r.stateNode.containerInfo;
            Q.nodeType === 1 ? Q.textContent = "" : Q.nodeType === 9 && Q.documentElement && Q.removeChild(Q.documentElement);
            break;
          case 5:
          case 6:
          case 4:
          case 17:
            break;
          default:
            throw Error(v(163));
        }
      } catch (Se) {
        Pn(r, r.return, Se);
      }
      if (n = r.sibling, n !== null) {
        n.return = r.return, qe = n;
        break;
      }
      qe = r.return;
    }
    return Xe = Np, Np = !1, Xe;
  }
  function Wu(n, r, o) {
    var s = r.updateQueue;
    if (s = s !== null ? s.lastEffect : null, s !== null) {
      var d = s = s.next;
      do {
        if ((d.tag & n) === n) {
          var h = d.destroy;
          d.destroy = void 0, h !== void 0 && Dp(r, o, h);
        }
        d = d.next;
      } while (d !== s);
    }
  }
  function $f(n, r) {
    if (r = r.updateQueue, r = r !== null ? r.lastEffect : null, r !== null) {
      var o = r = r.next;
      do {
        if ((o.tag & n) === n) {
          var s = o.create;
          o.destroy = s();
        }
        o = o.next;
      } while (o !== r);
    }
  }
  function Ff(n) {
    var r = n.ref;
    if (r !== null) {
      var o = n.stateNode;
      switch (n.tag) {
        case 5:
          n = o;
          break;
        default:
          n = o;
      }
      typeof r == "function" ? r(n) : r.current = n;
    }
  }
  function tm(n) {
    var r = n.alternate;
    r !== null && (n.alternate = null, tm(r)), n.child = null, n.deletions = null, n.sibling = null, n.tag === 5 && (r = n.stateNode, r !== null && (delete r[Ka], delete r[Hs], delete r[np], delete r[rp], delete r[Lu])), n.stateNode = null, n.return = null, n.dependencies = null, n.memoizedProps = null, n.memoizedState = null, n.pendingProps = null, n.stateNode = null, n.updateQueue = null;
  }
  function jf(n) {
    return n.tag === 5 || n.tag === 3 || n.tag === 4;
  }
  function lc(n) {
    e: for (; ; ) {
      for (; n.sibling === null; ) {
        if (n.return === null || jf(n.return)) return null;
        n = n.return;
      }
      for (n.sibling.return = n.return, n = n.sibling; n.tag !== 5 && n.tag !== 6 && n.tag !== 18; ) {
        if (n.flags & 2 || n.child === null || n.tag === 4) continue e;
        n.child.return = n, n = n.child;
      }
      if (!(n.flags & 2)) return n.stateNode;
    }
  }
  function Bi(n, r, o) {
    var s = n.tag;
    if (s === 5 || s === 6) n = n.stateNode, r ? o.nodeType === 8 ? o.parentNode.insertBefore(n, r) : o.insertBefore(n, r) : (o.nodeType === 8 ? (r = o.parentNode, r.insertBefore(n, o)) : (r = o, r.appendChild(n)), o = o._reactRootContainer, o != null || r.onclick !== null || (r.onclick = tf));
    else if (s !== 4 && (n = n.child, n !== null)) for (Bi(n, r, o), n = n.sibling; n !== null; ) Bi(n, r, o), n = n.sibling;
  }
  function Ii(n, r, o) {
    var s = n.tag;
    if (s === 5 || s === 6) n = n.stateNode, r ? o.insertBefore(n, r) : o.appendChild(n);
    else if (s !== 4 && (n = n.child, n !== null)) for (Ii(n, r, o), n = n.sibling; n !== null; ) Ii(n, r, o), n = n.sibling;
  }
  var An = null, Kr = !1;
  function ti(n, r, o) {
    for (o = o.child; o !== null; ) go(n, r, o), o = o.sibling;
  }
  function go(n, r, o) {
    if (sa && typeof sa.onCommitFiberUnmount == "function") try {
      sa.onCommitFiberUnmount(No, o);
    } catch {
    }
    switch (o.tag) {
      case 5:
        _r || Xo(o, r);
      case 6:
        var s = An, d = Kr;
        An = null, ti(n, r, o), An = s, Kr = d, An !== null && (Kr ? (n = An, o = o.stateNode, n.nodeType === 8 ? n.parentNode.removeChild(o) : n.removeChild(o)) : An.removeChild(o.stateNode));
        break;
      case 18:
        An !== null && (Kr ? (n = An, o = o.stateNode, n.nodeType === 8 ? Au(n.parentNode, o) : n.nodeType === 1 && Au(n, o), Ga(n)) : Au(An, o.stateNode));
        break;
      case 4:
        s = An, d = Kr, An = o.stateNode.containerInfo, Kr = !0, ti(n, r, o), An = s, Kr = d;
        break;
      case 0:
      case 11:
      case 14:
      case 15:
        if (!_r && (s = o.updateQueue, s !== null && (s = s.lastEffect, s !== null))) {
          d = s = s.next;
          do {
            var h = d, b = h.destroy;
            h = h.tag, b !== void 0 && (h & 2 || h & 4) && Dp(o, r, b), d = d.next;
          } while (d !== s);
        }
        ti(n, r, o);
        break;
      case 1:
        if (!_r && (Xo(o, r), s = o.stateNode, typeof s.componentWillUnmount == "function")) try {
          s.props = o.memoizedProps, s.state = o.memoizedState, s.componentWillUnmount();
        } catch (O) {
          Pn(o, r, O);
        }
        ti(n, r, o);
        break;
      case 21:
        ti(n, r, o);
        break;
      case 22:
        o.mode & 1 ? (_r = (s = _r) || o.memoizedState !== null, ti(n, r, o), _r = s) : ti(n, r, o);
        break;
      default:
        ti(n, r, o);
    }
  }
  function nm(n) {
    var r = n.updateQueue;
    if (r !== null) {
      n.updateQueue = null;
      var o = n.stateNode;
      o === null && (o = n.stateNode = new jg()), r.forEach(function(s) {
        var d = Wg.bind(null, n, s);
        o.has(s) || (o.add(s), s.then(d, d));
      });
    }
  }
  function bi(n, r) {
    var o = r.deletions;
    if (o !== null) for (var s = 0; s < o.length; s++) {
      var d = o[s];
      try {
        var h = n, b = r, O = b;
        e: for (; O !== null; ) {
          switch (O.tag) {
            case 5:
              An = O.stateNode, Kr = !1;
              break e;
            case 3:
              An = O.stateNode.containerInfo, Kr = !0;
              break e;
            case 4:
              An = O.stateNode.containerInfo, Kr = !0;
              break e;
          }
          O = O.return;
        }
        if (An === null) throw Error(v(160));
        go(h, b, d), An = null, Kr = !1;
        var P = d.alternate;
        P !== null && (P.return = null), d.return = null;
      } catch (J) {
        Pn(d, r, J);
      }
    }
    if (r.subtreeFlags & 12854) for (r = r.child; r !== null; ) rm(r, n), r = r.sibling;
  }
  function rm(n, r) {
    var o = n.alternate, s = n.flags;
    switch (n.tag) {
      case 0:
      case 11:
      case 14:
      case 15:
        if (bi(r, n), Ti(n), s & 4) {
          try {
            Wu(3, n, n.return), $f(3, n);
          } catch (Ze) {
            Pn(n, n.return, Ze);
          }
          try {
            Wu(5, n, n.return);
          } catch (Ze) {
            Pn(n, n.return, Ze);
          }
        }
        break;
      case 1:
        bi(r, n), Ti(n), s & 512 && o !== null && Xo(o, o.return);
        break;
      case 5:
        if (bi(r, n), Ti(n), s & 512 && o !== null && Xo(o, o.return), n.flags & 32) {
          var d = n.stateNode;
          try {
            ka(d, "");
          } catch (Ze) {
            Pn(n, n.return, Ze);
          }
        }
        if (s & 4 && (d = n.stateNode, d != null)) {
          var h = n.memoizedProps, b = o !== null ? o.memoizedProps : h, O = n.type, P = n.updateQueue;
          if (n.updateQueue = null, P !== null) try {
            O === "input" && h.type === "radio" && h.name != null && Ln(d, h), Rn(O, b);
            var J = Rn(O, h);
            for (b = 0; b < P.length; b += 2) {
              var ve = P[b], he = P[b + 1];
              ve === "style" ? Gt(d, he) : ve === "dangerouslySetInnerHTML" ? eo(d, he) : ve === "children" ? ka(d, he) : de(d, ve, he, J);
            }
            switch (O) {
              case "input":
                Gn(d, h);
                break;
              case "textarea":
                Pr(d, h);
                break;
              case "select":
                var pe = d._wrapperState.wasMultiple;
                d._wrapperState.wasMultiple = !!h.multiple;
                var Ve = h.value;
                Ve != null ? ir(d, !!h.multiple, Ve, !1) : pe !== !!h.multiple && (h.defaultValue != null ? ir(
                  d,
                  !!h.multiple,
                  h.defaultValue,
                  !0
                ) : ir(d, !!h.multiple, h.multiple ? [] : "", !1));
            }
            d[Hs] = h;
          } catch (Ze) {
            Pn(n, n.return, Ze);
          }
        }
        break;
      case 6:
        if (bi(r, n), Ti(n), s & 4) {
          if (n.stateNode === null) throw Error(v(162));
          d = n.stateNode, h = n.memoizedProps;
          try {
            d.nodeValue = h;
          } catch (Ze) {
            Pn(n, n.return, Ze);
          }
        }
        break;
      case 3:
        if (bi(r, n), Ti(n), s & 4 && o !== null && o.memoizedState.isDehydrated) try {
          Ga(r.containerInfo);
        } catch (Ze) {
          Pn(n, n.return, Ze);
        }
        break;
      case 4:
        bi(r, n), Ti(n);
        break;
      case 13:
        bi(r, n), Ti(n), d = n.child, d.flags & 8192 && (h = d.memoizedState !== null, d.stateNode.isHidden = h, !h || d.alternate !== null && d.alternate.memoizedState !== null || (Mp = qt())), s & 4 && nm(n);
        break;
      case 22:
        if (ve = o !== null && o.memoizedState !== null, n.mode & 1 ? (_r = (J = _r) || ve, bi(r, n), _r = J) : bi(r, n), Ti(n), s & 8192) {
          if (J = n.memoizedState !== null, (n.stateNode.isHidden = J) && !ve && n.mode & 1) for (qe = n, ve = n.child; ve !== null; ) {
            for (he = qe = ve; qe !== null; ) {
              switch (pe = qe, Ve = pe.child, pe.tag) {
                case 0:
                case 11:
                case 14:
                case 15:
                  Wu(4, pe, pe.return);
                  break;
                case 1:
                  Xo(pe, pe.return);
                  var Xe = pe.stateNode;
                  if (typeof Xe.componentWillUnmount == "function") {
                    s = pe, o = pe.return;
                    try {
                      r = s, Xe.props = r.memoizedProps, Xe.state = r.memoizedState, Xe.componentWillUnmount();
                    } catch (Ze) {
                      Pn(s, o, Ze);
                    }
                  }
                  break;
                case 5:
                  Xo(pe, pe.return);
                  break;
                case 22:
                  if (pe.memoizedState !== null) {
                    im(he);
                    continue;
                  }
              }
              Ve !== null ? (Ve.return = pe, qe = Ve) : im(he);
            }
            ve = ve.sibling;
          }
          e: for (ve = null, he = n; ; ) {
            if (he.tag === 5) {
              if (ve === null) {
                ve = he;
                try {
                  d = he.stateNode, J ? (h = d.style, typeof h.setProperty == "function" ? h.setProperty("display", "none", "important") : h.display = "none") : (O = he.stateNode, P = he.memoizedProps.style, b = P != null && P.hasOwnProperty("display") ? P.display : null, O.style.display = Rt("display", b));
                } catch (Ze) {
                  Pn(n, n.return, Ze);
                }
              }
            } else if (he.tag === 6) {
              if (ve === null) try {
                he.stateNode.nodeValue = J ? "" : he.memoizedProps;
              } catch (Ze) {
                Pn(n, n.return, Ze);
              }
            } else if ((he.tag !== 22 && he.tag !== 23 || he.memoizedState === null || he === n) && he.child !== null) {
              he.child.return = he, he = he.child;
              continue;
            }
            if (he === n) break e;
            for (; he.sibling === null; ) {
              if (he.return === null || he.return === n) break e;
              ve === he && (ve = null), he = he.return;
            }
            ve === he && (ve = null), he.sibling.return = he.return, he = he.sibling;
          }
        }
        break;
      case 19:
        bi(r, n), Ti(n), s & 4 && nm(n);
        break;
      case 21:
        break;
      default:
        bi(
          r,
          n
        ), Ti(n);
    }
  }
  function Ti(n) {
    var r = n.flags;
    if (r & 2) {
      try {
        e: {
          for (var o = n.return; o !== null; ) {
            if (jf(o)) {
              var s = o;
              break e;
            }
            o = o.return;
          }
          throw Error(v(160));
        }
        switch (s.tag) {
          case 5:
            var d = s.stateNode;
            s.flags & 32 && (ka(d, ""), s.flags &= -33);
            var h = lc(n);
            Ii(n, h, d);
            break;
          case 3:
          case 4:
            var b = s.stateNode.containerInfo, O = lc(n);
            Bi(n, O, b);
            break;
          default:
            throw Error(v(161));
        }
      } catch (P) {
        Pn(n, n.return, P);
      }
      n.flags &= -3;
    }
    r & 4096 && (n.flags &= -4097);
  }
  function uc(n, r, o) {
    qe = n, am(n);
  }
  function am(n, r, o) {
    for (var s = (n.mode & 1) !== 0; qe !== null; ) {
      var d = qe, h = d.child;
      if (d.tag === 22 && s) {
        var b = d.memoizedState !== null || Il;
        if (!b) {
          var O = d.alternate, P = O !== null && O.memoizedState !== null || _r;
          O = Il;
          var J = _r;
          if (Il = b, (_r = P) && !J) for (qe = d; qe !== null; ) b = qe, P = b.child, b.tag === 22 && b.memoizedState !== null ? sc(d) : P !== null ? (P.return = b, qe = P) : sc(d);
          for (; h !== null; ) qe = h, am(h), h = h.sibling;
          qe = d, Il = O, _r = J;
        }
        Ap(n);
      } else d.subtreeFlags & 8772 && h !== null ? (h.return = d, qe = h) : Ap(n);
    }
  }
  function Ap(n) {
    for (; qe !== null; ) {
      var r = qe;
      if (r.flags & 8772) {
        var o = r.alternate;
        try {
          if (r.flags & 8772) switch (r.tag) {
            case 0:
            case 11:
            case 15:
              _r || $f(5, r);
              break;
            case 1:
              var s = r.stateNode;
              if (r.flags & 4 && !_r) if (o === null) s.componentDidMount();
              else {
                var d = r.elementType === r.type ? o.memoizedProps : ya(r.type, o.memoizedProps);
                s.componentDidUpdate(d, o.memoizedState, s.__reactInternalSnapshotBeforeUpdate);
              }
              var h = r.updateQueue;
              h !== null && hp(r, h, s);
              break;
            case 3:
              var b = r.updateQueue;
              if (b !== null) {
                if (o = null, r.child !== null) switch (r.child.tag) {
                  case 5:
                    o = r.child.stateNode;
                    break;
                  case 1:
                    o = r.child.stateNode;
                }
                hp(r, b, o);
              }
              break;
            case 5:
              var O = r.stateNode;
              if (o === null && r.flags & 4) {
                o = O;
                var P = r.memoizedProps;
                switch (r.type) {
                  case "button":
                  case "input":
                  case "select":
                  case "textarea":
                    P.autoFocus && o.focus();
                    break;
                  case "img":
                    P.src && (o.src = P.src);
                }
              }
              break;
            case 6:
              break;
            case 4:
              break;
            case 12:
              break;
            case 13:
              if (r.memoizedState === null) {
                var J = r.alternate;
                if (J !== null) {
                  var ve = J.memoizedState;
                  if (ve !== null) {
                    var he = ve.dehydrated;
                    he !== null && Ga(he);
                  }
                }
              }
              break;
            case 19:
            case 17:
            case 21:
            case 22:
            case 23:
            case 25:
              break;
            default:
              throw Error(v(163));
          }
          _r || r.flags & 512 && Ff(r);
        } catch (pe) {
          Pn(r, r.return, pe);
        }
      }
      if (r === n) {
        qe = null;
        break;
      }
      if (o = r.sibling, o !== null) {
        o.return = r.return, qe = o;
        break;
      }
      qe = r.return;
    }
  }
  function im(n) {
    for (; qe !== null; ) {
      var r = qe;
      if (r === n) {
        qe = null;
        break;
      }
      var o = r.sibling;
      if (o !== null) {
        o.return = r.return, qe = o;
        break;
      }
      qe = r.return;
    }
  }
  function sc(n) {
    for (; qe !== null; ) {
      var r = qe;
      try {
        switch (r.tag) {
          case 0:
          case 11:
          case 15:
            var o = r.return;
            try {
              $f(4, r);
            } catch (P) {
              Pn(r, o, P);
            }
            break;
          case 1:
            var s = r.stateNode;
            if (typeof s.componentDidMount == "function") {
              var d = r.return;
              try {
                s.componentDidMount();
              } catch (P) {
                Pn(r, d, P);
              }
            }
            var h = r.return;
            try {
              Ff(r);
            } catch (P) {
              Pn(r, h, P);
            }
            break;
          case 5:
            var b = r.return;
            try {
              Ff(r);
            } catch (P) {
              Pn(r, b, P);
            }
        }
      } catch (P) {
        Pn(r, r.return, P);
      }
      if (r === n) {
        qe = null;
        break;
      }
      var O = r.sibling;
      if (O !== null) {
        O.return = r.return, qe = O;
        break;
      }
      qe = r.return;
    }
  }
  var om = Math.ceil, Hf = ue.ReactCurrentDispatcher, Yl = ue.ReactCurrentOwner, Br = ue.ReactCurrentBatchConfig, Mt = 0, tr = null, In = null, kr = 0, Ua = 0, Gu = pa(0), ur = 0, Wl = null, Gl = 0, Ql = 0, cc = 0, Qu = null, Ea = null, Mp = 0, qu = 1 / 0, So = null, Jo = !1, fc = null, ni = null, Vf = !1, Zo = null, dc = 0, Ku = 0, Xu = null, ql = -1, pc = 0;
  function yn() {
    return Mt & 6 ? qt() : ql !== -1 ? ql : ql = qt();
  }
  function Pa(n) {
    return n.mode & 1 ? Mt & 2 && kr !== 0 ? kr & -kr : Ul.transition !== null ? (pc === 0 && (pc = bl()), pc) : (n = Pt, n !== 0 || (n = window.event, n = n === void 0 ? 16 : xs(n.type)), n) : 1;
  }
  function $a(n, r, o, s) {
    if (50 < Ku) throw Ku = 0, Xu = null, Error(v(185));
    Lo(n, o, s), (!(Mt & 2) || n !== tr) && (n === tr && (!(Mt & 2) && (Ql |= o), ur === 4 && el(n, kr)), Sr(n, s), o === 1 && Mt === 0 && !(r.mode & 1) && (qu = qt() + 500, Bs && Qr()));
  }
  function Sr(n, r) {
    var o = n.callbackNode;
    hu(n, r);
    var s = Li(n, n === tr ? kr : 0);
    if (s === 0) o !== null && wn(o), n.callbackNode = null, n.callbackPriority = 0;
    else if (r = s & -s, n.callbackPriority !== r) {
      if (o != null && wn(o), r === 1) n.tag === 0 ? ap(yc.bind(null, n)) : jo(yc.bind(null, n)), Pg(function() {
        !(Mt & 6) && Qr();
      }), o = null;
      else {
        switch (ws(s)) {
          case 1:
            o = Et;
            break;
          case 4:
            o = Mi;
            break;
          case 16:
            o = ao;
            break;
          case 536870912:
            o = io;
            break;
          default:
            o = ao;
        }
        o = dm(o, lm.bind(null, n));
      }
      n.callbackPriority = r, n.callbackNode = o;
    }
  }
  function lm(n, r) {
    if (ql = -1, pc = 0, Mt & 6) throw Error(v(327));
    var o = n.callbackNode;
    if (Ju() && n.callbackNode !== o) return null;
    var s = Li(n, n === tr ? kr : 0);
    if (s === 0) return null;
    if (s & 30 || s & n.expiredLanes || r) r = Yf(n, s);
    else {
      r = s;
      var d = Mt;
      Mt |= 2;
      var h = um();
      (tr !== n || kr !== r) && (So = null, qu = qt() + 500, Xl(n, r));
      do
        try {
          Bg();
          break;
        } catch (O) {
          If(n, O);
        }
      while (!0);
      fp(), Hf.current = h, Mt = d, In !== null ? r = 0 : (tr = null, kr = 0, r = ur);
    }
    if (r !== 0) {
      if (r === 2 && (d = lo(n), d !== 0 && (s = d, r = vc(n, d))), r === 1) throw o = Wl, Xl(n, 0), el(n, s), Sr(n, qt()), o;
      if (r === 6) el(n, s);
      else {
        if (d = n.current.alternate, !(s & 30) && !mc(d) && (r = Yf(n, s), r === 2 && (h = lo(n), h !== 0 && (s = h, r = vc(n, h))), r === 1)) throw o = Wl, Xl(n, 0), el(n, s), Sr(n, qt()), o;
        switch (n.finishedWork = d, n.finishedLanes = s, r) {
          case 0:
          case 1:
            throw Error(v(345));
          case 2:
            Jl(n, Ea, So);
            break;
          case 3:
            if (el(n, s), (s & 130023424) === s && (r = Mp + 500 - qt(), 10 < r)) {
              if (Li(n, 0) !== 0) break;
              if (d = n.suspendedLanes, (d & s) !== s) {
                yn(), n.pingedLanes |= n.suspendedLanes & d;
                break;
              }
              n.timeoutHandle = nf(Jl.bind(null, n, Ea, So), r);
              break;
            }
            Jl(n, Ea, So);
            break;
          case 4:
            if (el(n, s), (s & 4194240) === s) break;
            for (r = n.eventTimes, d = -1; 0 < s; ) {
              var b = 31 - Yr(s);
              h = 1 << b, b = r[b], b > d && (d = b), s &= ~h;
            }
            if (s = d, s = qt() - s, s = (120 > s ? 120 : 480 > s ? 480 : 1080 > s ? 1080 : 1920 > s ? 1920 : 3e3 > s ? 3e3 : 4320 > s ? 4320 : 1960 * om(s / 1960)) - s, 10 < s) {
              n.timeoutHandle = nf(Jl.bind(null, n, Ea, So), s);
              break;
            }
            Jl(n, Ea, So);
            break;
          case 5:
            Jl(n, Ea, So);
            break;
          default:
            throw Error(v(329));
        }
      }
    }
    return Sr(n, qt()), n.callbackNode === o ? lm.bind(null, n) : null;
  }
  function vc(n, r) {
    var o = Qu;
    return n.current.memoizedState.isDehydrated && (Xl(n, r).flags |= 256), n = Yf(n, r), n !== 2 && (r = Ea, Ea = o, r !== null && hc(r)), n;
  }
  function hc(n) {
    Ea === null ? Ea = n : Ea.push.apply(Ea, n);
  }
  function mc(n) {
    for (var r = n; ; ) {
      if (r.flags & 16384) {
        var o = r.updateQueue;
        if (o !== null && (o = o.stores, o !== null)) for (var s = 0; s < o.length; s++) {
          var d = o[s], h = d.getSnapshot;
          d = d.value;
          try {
            if (!yi(h(), d)) return !1;
          } catch {
            return !1;
          }
        }
      }
      if (o = r.child, r.subtreeFlags & 16384 && o !== null) o.return = r, r = o;
      else {
        if (r === n) break;
        for (; r.sibling === null; ) {
          if (r.return === null || r.return === n) return !0;
          r = r.return;
        }
        r.sibling.return = r.return, r = r.sibling;
      }
    }
    return !0;
  }
  function el(n, r) {
    for (r &= ~cc, r &= ~Ql, n.suspendedLanes |= r, n.pingedLanes &= ~r, n = n.expirationTimes; 0 < r; ) {
      var o = 31 - Yr(r), s = 1 << o;
      n[o] = -1, r &= ~s;
    }
  }
  function yc(n) {
    if (Mt & 6) throw Error(v(327));
    Ju();
    var r = Li(n, 0);
    if (!(r & 1)) return Sr(n, qt()), null;
    var o = Yf(n, r);
    if (n.tag !== 0 && o === 2) {
      var s = lo(n);
      s !== 0 && (r = s, o = vc(n, s));
    }
    if (o === 1) throw o = Wl, Xl(n, 0), el(n, r), Sr(n, qt()), o;
    if (o === 6) throw Error(v(345));
    return n.finishedWork = n.current.alternate, n.finishedLanes = r, Jl(n, Ea, So), Sr(n, qt()), null;
  }
  function Bf(n, r) {
    var o = Mt;
    Mt |= 1;
    try {
      return n(r);
    } finally {
      Mt = o, Mt === 0 && (qu = qt() + 500, Bs && Qr());
    }
  }
  function Kl(n) {
    Zo !== null && Zo.tag === 0 && !(Mt & 6) && Ju();
    var r = Mt;
    Mt |= 1;
    var o = Br.transition, s = Pt;
    try {
      if (Br.transition = null, Pt = 1, n) return n();
    } finally {
      Pt = s, Br.transition = o, Mt = r, !(Mt & 6) && Qr();
    }
  }
  function Lp() {
    Ua = Gu.current, sn(Gu);
  }
  function Xl(n, r) {
    n.finishedWork = null, n.finishedLanes = 0;
    var o = n.timeoutHandle;
    if (o !== -1 && (n.timeoutHandle = -1, Lh(o)), In !== null) for (o = In.return; o !== null; ) {
      var s = o;
      switch (lf(s), s.tag) {
        case 1:
          s = s.type.childContextTypes, s != null && Fi();
          break;
        case 3:
          Fu(), sn(Xn), sn(Un), qs();
          break;
        case 5:
          gp(s);
          break;
        case 4:
          Fu();
          break;
        case 13:
          sn(Nn);
          break;
        case 19:
          sn(Nn);
          break;
        case 10:
          dp(s.type._context);
          break;
        case 22:
        case 23:
          Lp();
      }
      o = o.return;
    }
    if (tr = n, In = n = tl(n.current, null), kr = Ua = r, ur = 0, Wl = null, cc = Ql = Gl = 0, Ea = Qu = null, Pl !== null) {
      for (r = 0; r < Pl.length; r++) if (o = Pl[r], s = o.interleaved, s !== null) {
        o.interleaved = null;
        var d = s.next, h = o.pending;
        if (h !== null) {
          var b = h.next;
          h.next = d, s.next = b;
        }
        o.pending = s;
      }
      Pl = null;
    }
    return n;
  }
  function If(n, r) {
    do {
      var o = In;
      try {
        if (fp(), rt.current = tn, ff) {
          for (var s = Ct.memoizedState; s !== null; ) {
            var d = s.queue;
            d !== null && (d.pending = null), s = s.next;
          }
          ff = !1;
        }
        if (zt = 0, or = cn = Ct = null, Ks = !1, Xs = 0, Yl.current = null, o === null || o.return === null) {
          ur = 1, Wl = r, In = null;
          break;
        }
        e: {
          var h = n, b = o.return, O = o, P = r;
          if (r = kr, O.flags |= 32768, P !== null && typeof P == "object" && typeof P.then == "function") {
            var J = P, ve = O, he = ve.tag;
            if (!(ve.mode & 1) && (he === 0 || he === 11 || he === 15)) {
              var pe = ve.alternate;
              pe ? (ve.updateQueue = pe.updateQueue, ve.memoizedState = pe.memoizedState, ve.lanes = pe.lanes) : (ve.updateQueue = null, ve.memoizedState = null);
            }
            var Ve = wp(b);
            if (Ve !== null) {
              Ve.flags &= -257, Kh(Ve, b, O, h, r), Ve.mode & 1 && Rp(h, J, r), r = Ve, P = J;
              var Xe = r.updateQueue;
              if (Xe === null) {
                var Ze = /* @__PURE__ */ new Set();
                Ze.add(P), r.updateQueue = Ze;
              } else Xe.add(P);
              break e;
            } else {
              if (!(r & 1)) {
                Rp(h, J, r), zp();
                break e;
              }
              P = Error(v(426));
            }
          } else if (xn && O.mode & 1) {
            var Yn = wp(b);
            if (Yn !== null) {
              !(Yn.flags & 65536) && (Yn.flags |= 256), Kh(Yn, b, O, h, r), Ys(Ko(P, O));
              break e;
            }
          }
          h = P = Ko(P, O), ur !== 4 && (ur = 2), Qu === null ? Qu = [h] : Qu.push(h), h = b;
          do {
            switch (h.tag) {
              case 3:
                h.flags |= 65536, r &= -r, h.lanes |= r;
                var Y = rc(h, P, r);
                Bh(h, Y);
                break e;
              case 1:
                O = P;
                var H = h.type, Q = h.stateNode;
                if (!(h.flags & 128) && (typeof H.getDerivedStateFromError == "function" || Q !== null && typeof Q.componentDidCatch == "function" && (ni === null || !ni.has(Q)))) {
                  h.flags |= 65536, r &= -r, h.lanes |= r;
                  var Se = qh(h, O, r);
                  Bh(h, Se);
                  break e;
                }
            }
            h = h.return;
          } while (h !== null);
        }
        sm(o);
      } catch ($e) {
        r = $e, In === o && o !== null && (In = o = o.return);
        continue;
      }
      break;
    } while (!0);
  }
  function um() {
    var n = Hf.current;
    return Hf.current = tn, n === null ? tn : n;
  }
  function zp() {
    (ur === 0 || ur === 3 || ur === 2) && (ur = 4), tr === null || !(Gl & 268435455) && !(Ql & 268435455) || el(tr, kr);
  }
  function Yf(n, r) {
    var o = Mt;
    Mt |= 2;
    var s = um();
    (tr !== n || kr !== r) && (So = null, Xl(n, r));
    do
      try {
        Vg();
        break;
      } catch (d) {
        If(n, d);
      }
    while (!0);
    if (fp(), Mt = o, Hf.current = s, In !== null) throw Error(v(261));
    return tr = null, kr = 0, ur;
  }
  function Vg() {
    for (; In !== null; ) Up(In);
  }
  function Bg() {
    for (; In !== null && !$r(); ) Up(In);
  }
  function Up(n) {
    var r = $p(n.alternate, n, Ua);
    n.memoizedProps = n.pendingProps, r === null ? sm(n) : In = r, Yl.current = null;
  }
  function sm(n) {
    var r = n;
    do {
      var o = r.alternate;
      if (n = r.return, r.flags & 32768) {
        if (o = em(o, r), o !== null) {
          o.flags &= 32767, In = o;
          return;
        }
        if (n !== null) n.flags |= 32768, n.subtreeFlags = 0, n.deletions = null;
        else {
          ur = 6, In = null;
          return;
        }
      } else if (o = Op(o, r, Ua), o !== null) {
        In = o;
        return;
      }
      if (r = r.sibling, r !== null) {
        In = r;
        return;
      }
      In = r = n;
    } while (r !== null);
    ur === 0 && (ur = 5);
  }
  function Jl(n, r, o) {
    var s = Pt, d = Br.transition;
    try {
      Br.transition = null, Pt = 1, Ig(n, r, o, s);
    } finally {
      Br.transition = d, Pt = s;
    }
    return null;
  }
  function Ig(n, r, o, s) {
    do
      Ju();
    while (Zo !== null);
    if (Mt & 6) throw Error(v(327));
    o = n.finishedWork;
    var d = n.finishedLanes;
    if (o === null) return null;
    if (n.finishedWork = null, n.finishedLanes = 0, o === n.current) throw Error(v(177));
    n.callbackNode = null, n.callbackPriority = 0;
    var h = o.lanes | o.childLanes;
    if (Ts(n, h), n === tr && (In = tr = null, kr = 0), !(o.subtreeFlags & 2064) && !(o.flags & 2064) || Vf || (Vf = !0, dm(ao, function() {
      return Ju(), null;
    })), h = (o.flags & 15990) !== 0, o.subtreeFlags & 15990 || h) {
      h = Br.transition, Br.transition = null;
      var b = Pt;
      Pt = 1;
      var O = Mt;
      Mt |= 4, Yl.current = null, Hg(n, o), rm(o, n), wh(js), zo = !!Nl, js = Nl = null, n.current = o, uc(o), vi(), Mt = O, Pt = b, Br.transition = h;
    } else n.current = o;
    if (Vf && (Vf = !1, Zo = n, dc = d), h = n.pendingLanes, h === 0 && (ni = null), Cs(o.stateNode), Sr(n, qt()), r !== null) for (s = n.onRecoverableError, o = 0; o < r.length; o++) d = r[o], s(d.value, { componentStack: d.stack, digest: d.digest });
    if (Jo) throw Jo = !1, n = fc, fc = null, n;
    return dc & 1 && n.tag !== 0 && Ju(), h = n.pendingLanes, h & 1 ? n === Xu ? Ku++ : (Ku = 0, Xu = n) : Ku = 0, Qr(), null;
  }
  function Ju() {
    if (Zo !== null) {
      var n = ws(dc), r = Br.transition, o = Pt;
      try {
        if (Br.transition = null, Pt = 16 > n ? 16 : n, Zo === null) var s = !1;
        else {
          if (n = Zo, Zo = null, dc = 0, Mt & 6) throw Error(v(331));
          var d = Mt;
          for (Mt |= 4, qe = n.current; qe !== null; ) {
            var h = qe, b = h.child;
            if (qe.flags & 16) {
              var O = h.deletions;
              if (O !== null) {
                for (var P = 0; P < O.length; P++) {
                  var J = O[P];
                  for (qe = J; qe !== null; ) {
                    var ve = qe;
                    switch (ve.tag) {
                      case 0:
                      case 11:
                      case 15:
                        Wu(8, ve, h);
                    }
                    var he = ve.child;
                    if (he !== null) he.return = ve, qe = he;
                    else for (; qe !== null; ) {
                      ve = qe;
                      var pe = ve.sibling, Ve = ve.return;
                      if (tm(ve), ve === J) {
                        qe = null;
                        break;
                      }
                      if (pe !== null) {
                        pe.return = Ve, qe = pe;
                        break;
                      }
                      qe = Ve;
                    }
                  }
                }
                var Xe = h.alternate;
                if (Xe !== null) {
                  var Ze = Xe.child;
                  if (Ze !== null) {
                    Xe.child = null;
                    do {
                      var Yn = Ze.sibling;
                      Ze.sibling = null, Ze = Yn;
                    } while (Ze !== null);
                  }
                }
                qe = h;
              }
            }
            if (h.subtreeFlags & 2064 && b !== null) b.return = h, qe = b;
            else e: for (; qe !== null; ) {
              if (h = qe, h.flags & 2048) switch (h.tag) {
                case 0:
                case 11:
                case 15:
                  Wu(9, h, h.return);
              }
              var Y = h.sibling;
              if (Y !== null) {
                Y.return = h.return, qe = Y;
                break e;
              }
              qe = h.return;
            }
          }
          var H = n.current;
          for (qe = H; qe !== null; ) {
            b = qe;
            var Q = b.child;
            if (b.subtreeFlags & 2064 && Q !== null) Q.return = b, qe = Q;
            else e: for (b = H; qe !== null; ) {
              if (O = qe, O.flags & 2048) try {
                switch (O.tag) {
                  case 0:
                  case 11:
                  case 15:
                    $f(9, O);
                }
              } catch ($e) {
                Pn(O, O.return, $e);
              }
              if (O === b) {
                qe = null;
                break e;
              }
              var Se = O.sibling;
              if (Se !== null) {
                Se.return = O.return, qe = Se;
                break e;
              }
              qe = O.return;
            }
          }
          if (Mt = d, Qr(), sa && typeof sa.onPostCommitFiberRoot == "function") try {
            sa.onPostCommitFiberRoot(No, n);
          } catch {
          }
          s = !0;
        }
        return s;
      } finally {
        Pt = o, Br.transition = r;
      }
    }
    return !1;
  }
  function cm(n, r, o) {
    r = Ko(o, r), r = rc(n, r, 1), n = Wo(n, r, 1), r = yn(), n !== null && (Lo(n, 1, r), Sr(n, r));
  }
  function Pn(n, r, o) {
    if (n.tag === 3) cm(n, n, o);
    else for (; r !== null; ) {
      if (r.tag === 3) {
        cm(r, n, o);
        break;
      } else if (r.tag === 1) {
        var s = r.stateNode;
        if (typeof r.type.getDerivedStateFromError == "function" || typeof s.componentDidCatch == "function" && (ni === null || !ni.has(s))) {
          n = Ko(o, n), n = qh(r, n, 1), r = Wo(r, n, 1), n = yn(), r !== null && (Lo(r, 1, n), Sr(r, n));
          break;
        }
      }
      r = r.return;
    }
  }
  function Pp(n, r, o) {
    var s = n.pingCache;
    s !== null && s.delete(r), r = yn(), n.pingedLanes |= n.suspendedLanes & o, tr === n && (kr & o) === o && (ur === 4 || ur === 3 && (kr & 130023424) === kr && 500 > qt() - Mp ? Xl(n, 0) : cc |= o), Sr(n, r);
  }
  function fm(n, r) {
    r === 0 && (n.mode & 1 ? (r = Ao, Ao <<= 1, !(Ao & 130023424) && (Ao = 4194304)) : r = 1);
    var o = yn();
    n = Hi(n, r), n !== null && (Lo(n, r, o), Sr(n, o));
  }
  function Yg(n) {
    var r = n.memoizedState, o = 0;
    r !== null && (o = r.retryLane), fm(n, o);
  }
  function Wg(n, r) {
    var o = 0;
    switch (n.tag) {
      case 13:
        var s = n.stateNode, d = n.memoizedState;
        d !== null && (o = d.retryLane);
        break;
      case 19:
        s = n.stateNode;
        break;
      default:
        throw Error(v(314));
    }
    s !== null && s.delete(r), fm(n, o);
  }
  var $p;
  $p = function(n, r, o) {
    if (n !== null) if (n.memoizedProps !== r.pendingProps || Xn.current) gr = !0;
    else {
      if (!(n.lanes & o) && !(r.flags & 128)) return gr = !1, Pf(n, r, o);
      gr = !!(n.flags & 131072);
    }
    else gr = !1, xn && r.flags & 1048576 && Uh(r, Bo, r.index);
    switch (r.lanes = 0, r.tag) {
      case 2:
        var s = r.type;
        ei(n, r), n = r.pendingProps;
        var d = Aa(r, Un.current);
        Pu(r, o), d = ct(null, r, s, n, d, o);
        var h = Go();
        return r.flags |= 1, typeof d == "object" && d !== null && typeof d.render == "function" && d.$$typeof === void 0 ? (r.tag = 1, r.memoizedState = null, r.updateQueue = null, Jn(s) ? (h = !0, Ll(r)) : h = !1, r.memoizedState = d.state !== null && d.state !== void 0 ? d.state : null, Yo(r), d.updater = kf, r.stateNode = d, d._reactInternals = r, bp(r, s, n, o), r = xp(null, r, s, !0, h, o)) : (r.tag = 0, xn && h && ip(r), Bn(null, r, d, o), r = r.child), r;
      case 16:
        s = r.elementType;
        e: {
          switch (ei(n, r), n = r.pendingProps, d = s._init, s = d(s._payload), r.type = s, d = r.tag = Qg(s), n = ya(s, n), d) {
            case 0:
              r = Af(null, r, s, n, o);
              break e;
            case 1:
              r = Fg(null, r, s, n, o);
              break e;
            case 11:
              r = Nf(null, r, s, n, o);
              break e;
            case 14:
              r = ga(null, r, s, ya(s.type, n), o);
              break e;
          }
          throw Error(v(
            306,
            s,
            ""
          ));
        }
        return r;
      case 0:
        return s = r.type, d = r.pendingProps, d = r.elementType === s ? d : ya(s, d), Af(n, r, s, d, o);
      case 1:
        return s = r.type, d = r.pendingProps, d = r.elementType === s ? d : ya(s, d), Fg(n, r, s, d, o);
      case 3:
        e: {
          if (Mf(r), n === null) throw Error(v(387));
          s = r.pendingProps, h = r.memoizedState, d = h.element, Vh(n, r), sf(r, s, null, o);
          var b = r.memoizedState;
          if (s = b.element, h.isDehydrated) if (h = { element: s, isDehydrated: !1, cache: b.cache, pendingSuspenseBoundaries: b.pendingSuspenseBoundaries, transitions: b.transitions }, r.updateQueue.baseState = h, r.memoizedState = h, r.flags & 256) {
            d = Ko(Error(v(423)), r), r = Iu(n, r, s, o, d);
            break e;
          } else if (s !== d) {
            d = Ko(Error(v(424)), r), r = Iu(n, r, s, o, d);
            break e;
          } else for (ha = gi(r.stateNode.containerInfo.firstChild), va = r, xn = !0, Ei = null, o = wr(r, null, s, o), r.child = o; o; ) o.flags = o.flags & -3 | 4096, o = o.sibling;
          else {
            if (mo(), s === d) {
              r = xr(n, r, o);
              break e;
            }
            Bn(n, r, s, o);
          }
          r = r.child;
        }
        return r;
      case 5:
        return yp(r), n === null && sp(r), s = r.type, d = r.pendingProps, h = n !== null ? n.memoizedProps : null, b = d.children, Al(s, d) ? b = null : h !== null && Al(s, h) && (r.flags |= 32), ac(n, r), Bn(n, r, b, o), r.child;
      case 6:
        return n === null && sp(r), null;
      case 13:
        return Xh(n, r, o);
      case 4:
        return mp(r, r.stateNode.containerInfo), s = r.pendingProps, n === null ? r.child = Ci(r, null, s, o) : Bn(n, r, s, o), r.child;
      case 11:
        return s = r.type, d = r.pendingProps, d = r.elementType === s ? d : ya(s, d), Nf(n, r, s, d, o);
      case 7:
        return Bn(n, r, r.pendingProps, o), r.child;
      case 8:
        return Bn(n, r, r.pendingProps.children, o), r.child;
      case 12:
        return Bn(n, r, r.pendingProps.children, o), r.child;
      case 10:
        e: {
          if (s = r.type._context, d = r.pendingProps, h = r.memoizedProps, b = d.value, mn(Ne, s._currentValue), s._currentValue = b, h !== null) if (yi(h.value, b)) {
            if (h.children === d.children && !Xn.current) {
              r = xr(n, r, o);
              break e;
            }
          } else for (h = r.child, h !== null && (h.return = r); h !== null; ) {
            var O = h.dependencies;
            if (O !== null) {
              b = h.child;
              for (var P = O.firstContext; P !== null; ) {
                if (P.context === s) {
                  if (h.tag === 1) {
                    P = yo(-1, o & -o), P.tag = 2;
                    var J = h.updateQueue;
                    if (J !== null) {
                      J = J.shared;
                      var ve = J.pending;
                      ve === null ? P.next = P : (P.next = ve.next, ve.next = P), J.pending = P;
                    }
                  }
                  h.lanes |= o, P = h.alternate, P !== null && (P.lanes |= o), pp(
                    h.return,
                    o,
                    r
                  ), O.lanes |= o;
                  break;
                }
                P = P.next;
              }
            } else if (h.tag === 10) b = h.type === r.type ? null : h.child;
            else if (h.tag === 18) {
              if (b = h.return, b === null) throw Error(v(341));
              b.lanes |= o, O = b.alternate, O !== null && (O.lanes |= o), pp(b, o, r), b = h.sibling;
            } else b = h.child;
            if (b !== null) b.return = h;
            else for (b = h; b !== null; ) {
              if (b === r) {
                b = null;
                break;
              }
              if (h = b.sibling, h !== null) {
                h.return = b.return, b = h;
                break;
              }
              b = b.return;
            }
            h = b;
          }
          Bn(n, r, d.children, o), r = r.child;
        }
        return r;
      case 9:
        return d = r.type, s = r.pendingProps.children, Pu(r, o), d = en(d), s = s(d), r.flags |= 1, Bn(n, r, s, o), r.child;
      case 14:
        return s = r.type, d = ya(s, r.pendingProps), d = ya(s.type, d), ga(n, r, s, d, o);
      case 15:
        return Bl(n, r, r.type, r.pendingProps, o);
      case 17:
        return s = r.type, d = r.pendingProps, d = r.elementType === s ? d : ya(s, d), ei(n, r), r.tag = 1, Jn(s) ? (n = !0, Ll(r)) : n = !1, Pu(r, o), Qh(r, s, d), bp(r, s, d, o), xp(null, r, s, !0, n, o);
      case 19:
        return Sa(n, r, o);
      case 22:
        return Tt(n, r, o);
    }
    throw Error(v(156, r.tag));
  };
  function dm(n, r) {
    return Sn(n, r);
  }
  function Gg(n, r, o, s) {
    this.tag = n, this.key = o, this.sibling = this.child = this.return = this.stateNode = this.type = this.elementType = null, this.index = 0, this.ref = null, this.pendingProps = r, this.dependencies = this.memoizedState = this.updateQueue = this.memoizedProps = null, this.mode = s, this.subtreeFlags = this.flags = 0, this.deletions = null, this.childLanes = this.lanes = 0, this.alternate = null;
  }
  function ri(n, r, o, s) {
    return new Gg(n, r, o, s);
  }
  function Fp(n) {
    return n = n.prototype, !(!n || !n.isReactComponent);
  }
  function Qg(n) {
    if (typeof n == "function") return Fp(n) ? 1 : 0;
    if (n != null) {
      if (n = n.$$typeof, n === je) return 11;
      if (n === pt) return 14;
    }
    return 2;
  }
  function tl(n, r) {
    var o = n.alternate;
    return o === null ? (o = ri(n.tag, r, n.key, n.mode), o.elementType = n.elementType, o.type = n.type, o.stateNode = n.stateNode, o.alternate = n, n.alternate = o) : (o.pendingProps = r, o.type = n.type, o.flags = 0, o.subtreeFlags = 0, o.deletions = null), o.flags = n.flags & 14680064, o.childLanes = n.childLanes, o.lanes = n.lanes, o.child = n.child, o.memoizedProps = n.memoizedProps, o.memoizedState = n.memoizedState, o.updateQueue = n.updateQueue, r = n.dependencies, o.dependencies = r === null ? null : { lanes: r.lanes, firstContext: r.firstContext }, o.sibling = n.sibling, o.index = n.index, o.ref = n.ref, o;
  }
  function Wf(n, r, o, s, d, h) {
    var b = 2;
    if (s = n, typeof n == "function") Fp(n) && (b = 1);
    else if (typeof n == "string") b = 5;
    else e: switch (n) {
      case Ce:
        return nl(o.children, d, h, r);
      case Ge:
        b = 8, d |= 8;
        break;
      case _t:
        return n = ri(12, o, r, d | 2), n.elementType = _t, n.lanes = h, n;
      case Qe:
        return n = ri(13, o, r, d), n.elementType = Qe, n.lanes = h, n;
      case Pe:
        return n = ri(19, o, r, d), n.elementType = Pe, n.lanes = h, n;
      case ot:
        return Zu(o, d, h, r);
      default:
        if (typeof n == "object" && n !== null) switch (n.$$typeof) {
          case x:
            b = 10;
            break e;
          case ge:
            b = 9;
            break e;
          case je:
            b = 11;
            break e;
          case pt:
            b = 14;
            break e;
          case vt:
            b = 16, s = null;
            break e;
        }
        throw Error(v(130, n == null ? n : typeof n, ""));
    }
    return r = ri(b, o, r, d), r.elementType = n, r.type = s, r.lanes = h, r;
  }
  function nl(n, r, o, s) {
    return n = ri(7, n, s, r), n.lanes = o, n;
  }
  function Zu(n, r, o, s) {
    return n = ri(22, n, s, r), n.elementType = ot, n.lanes = o, n.stateNode = { isHidden: !1 }, n;
  }
  function Zl(n, r, o) {
    return n = ri(6, n, null, r), n.lanes = o, n;
  }
  function jp(n, r, o) {
    return r = ri(4, n.children !== null ? n.children : [], n.key, r), r.lanes = o, r.stateNode = { containerInfo: n.containerInfo, pendingChildren: null, implementation: n.implementation }, r;
  }
  function pm(n, r, o, s, d) {
    this.tag = r, this.containerInfo = n, this.finishedWork = this.pingCache = this.current = this.pendingChildren = null, this.timeoutHandle = -1, this.callbackNode = this.pendingContext = this.context = null, this.callbackPriority = 0, this.eventTimes = Tl(0), this.expirationTimes = Tl(-1), this.entangledLanes = this.finishedLanes = this.mutableReadLanes = this.expiredLanes = this.pingedLanes = this.suspendedLanes = this.pendingLanes = 0, this.entanglements = Tl(0), this.identifierPrefix = s, this.onRecoverableError = d, this.mutableSourceEagerHydrationData = null;
  }
  function Gf(n, r, o, s, d, h, b, O, P) {
    return n = new pm(n, r, o, O, P), r === 1 ? (r = 1, h === !0 && (r |= 8)) : r = 0, h = ri(3, null, null, r), n.current = h, h.stateNode = n, h.memoizedState = { element: s, isDehydrated: o, cache: null, transitions: null, pendingSuspenseBoundaries: null }, Yo(h), n;
  }
  function vm(n, r, o) {
    var s = 3 < arguments.length && arguments[3] !== void 0 ? arguments[3] : null;
    return { $$typeof: se, key: s == null ? null : "" + s, children: n, containerInfo: r, implementation: o };
  }
  function hm(n) {
    if (!n) return Ot;
    n = n._reactInternals;
    e: {
      if (Ue(n) !== n || n.tag !== 1) throw Error(v(170));
      var r = n;
      do {
        switch (r.tag) {
          case 3:
            r = r.stateNode.context;
            break e;
          case 1:
            if (Jn(r.type)) {
              r = r.stateNode.__reactInternalMemoizedMergedChildContext;
              break e;
            }
        }
        r = r.return;
      } while (r !== null);
      throw Error(v(171));
    }
    if (n.tag === 1) {
      var o = n.type;
      if (Jn(o)) return zh(n, o, r);
    }
    return r;
  }
  function Hp(n, r, o, s, d, h, b, O, P) {
    return n = Gf(o, s, !0, n, d, h, b, O, P), n.context = hm(null), o = n.current, s = yn(), d = Pa(o), h = yo(s, d), h.callback = r ?? null, Wo(o, h, d), n.current.lanes = d, Lo(n, d, s), Sr(n, s), n;
  }
  function Qf(n, r, o, s) {
    var d = r.current, h = yn(), b = Pa(d);
    return o = hm(o), r.context === null ? r.context = o : r.pendingContext = o, r = yo(h, b), r.payload = { element: n }, s = s === void 0 ? null : s, s !== null && (r.callback = s), n = Wo(d, r, b), n !== null && ($a(n, d, b, h), uf(n, d, b)), b;
  }
  function qf(n) {
    if (n = n.current, !n.child) return null;
    switch (n.child.tag) {
      case 5:
        return n.child.stateNode;
      default:
        return n.child.stateNode;
    }
  }
  function mm(n, r) {
    if (n = n.memoizedState, n !== null && n.dehydrated !== null) {
      var o = n.retryLane;
      n.retryLane = o !== 0 && o < r ? o : r;
    }
  }
  function Kf(n, r) {
    mm(n, r), (n = n.alternate) && mm(n, r);
  }
  function ym() {
    return null;
  }
  var Vp = typeof reportError == "function" ? reportError : function(n) {
    console.error(n);
  };
  function rl(n) {
    this._internalRoot = n;
  }
  Xf.prototype.render = rl.prototype.render = function(n) {
    var r = this._internalRoot;
    if (r === null) throw Error(v(409));
    Qf(n, r, null, null);
  }, Xf.prototype.unmount = rl.prototype.unmount = function() {
    var n = this._internalRoot;
    if (n !== null) {
      this._internalRoot = null;
      var r = n.containerInfo;
      Kl(function() {
        Qf(null, n, null, null);
      }), r[vo] = null;
    }
  };
  function Xf(n) {
    this._internalRoot = n;
  }
  Xf.prototype.unstable_scheduleHydration = function(n) {
    if (n) {
      var r = zi();
      n = { blockedOn: null, target: n, priority: r };
      for (var o = 0; o < hi.length && r !== 0 && r < hi[o].priority; o++) ;
      hi.splice(o, 0, n), o === 0 && yu(n);
    }
  };
  function Bp(n) {
    return !(!n || n.nodeType !== 1 && n.nodeType !== 9 && n.nodeType !== 11);
  }
  function Jf(n) {
    return !(!n || n.nodeType !== 1 && n.nodeType !== 9 && n.nodeType !== 11 && (n.nodeType !== 8 || n.nodeValue !== " react-mount-point-unstable "));
  }
  function gm() {
  }
  function qg(n, r, o, s, d) {
    if (d) {
      if (typeof s == "function") {
        var h = s;
        s = function() {
          var J = qf(b);
          h.call(J);
        };
      }
      var b = Hp(r, s, n, 0, null, !1, !1, "", gm);
      return n._reactRootContainer = b, n[vo] = b.current, $s(n.nodeType === 8 ? n.parentNode : n), Kl(), b;
    }
    for (; d = n.lastChild; ) n.removeChild(d);
    if (typeof s == "function") {
      var O = s;
      s = function() {
        var J = qf(P);
        O.call(J);
      };
    }
    var P = Gf(n, 0, !1, null, null, !1, !1, "", gm);
    return n._reactRootContainer = P, n[vo] = P.current, $s(n.nodeType === 8 ? n.parentNode : n), Kl(function() {
      Qf(r, P, o, s);
    }), P;
  }
  function Zf(n, r, o, s, d) {
    var h = o._reactRootContainer;
    if (h) {
      var b = h;
      if (typeof d == "function") {
        var O = d;
        d = function() {
          var P = qf(b);
          O.call(P);
        };
      }
      Qf(r, b, n, d);
    } else b = qg(o, r, n, d, s);
    return qf(b);
  }
  mu = function(n) {
    switch (n.tag) {
      case 3:
        var r = n.stateNode;
        if (r.current.memoizedState.isDehydrated) {
          var o = ca(r.pendingLanes);
          o !== 0 && (Rs(r, o | 1), Sr(r, qt()), !(Mt & 6) && (qu = qt() + 500, Qr()));
        }
        break;
      case 13:
        Kl(function() {
          var s = Hi(n, 1);
          if (s !== null) {
            var d = yn();
            $a(s, n, 1, d);
          }
        }), Kf(n, 1);
    }
  }, $t = function(n) {
    if (n.tag === 13) {
      var r = Hi(n, 134217728);
      if (r !== null) {
        var o = yn();
        $a(r, n, 134217728, o);
      }
      Kf(n, 134217728);
    }
  }, Bc = function(n) {
    if (n.tag === 13) {
      var r = Pa(n), o = Hi(n, r);
      if (o !== null) {
        var s = yn();
        $a(o, n, r, s);
      }
      Kf(n, r);
    }
  }, zi = function() {
    return Pt;
  }, ht = function(n, r) {
    var o = Pt;
    try {
      return Pt = n, r();
    } finally {
      Pt = o;
    }
  }, an = function(n, r, o) {
    switch (r) {
      case "input":
        if (Gn(n, o), r = o.name, o.type === "radio" && r != null) {
          for (o = n; o.parentNode; ) o = o.parentNode;
          for (o = o.querySelectorAll("input[name=" + JSON.stringify("" + r) + '][type="radio"]'), r = 0; r < o.length; r++) {
            var s = o[r];
            if (s !== n && s.form === n.form) {
              var d = ho(s);
              if (!d) throw Error(v(90));
              Ht(s), Gn(s, d);
            }
          }
        }
        break;
      case "textarea":
        Pr(n, o);
        break;
      case "select":
        r = o.value, r != null && ir(n, !!o.multiple, r, !1);
    }
  }, Sl = Bf, El = Kl;
  var Sm = { usingClientEntryPoint: !1, Events: [Vs, nt, ho, Ya, to, Bf] }, gc = { findFiberByHostInstance: Ml, bundleType: 0, version: "18.3.1", rendererPackageName: "react-dom" }, Kg = { bundleType: gc.bundleType, version: gc.version, rendererPackageName: gc.rendererPackageName, rendererConfig: gc.rendererConfig, overrideHookState: null, overrideHookStateDeletePath: null, overrideHookStateRenamePath: null, overrideProps: null, overridePropsDeletePath: null, overridePropsRenamePath: null, setErrorHandler: null, setSuspenseHandler: null, scheduleUpdate: null, currentDispatcherRef: ue.ReactCurrentDispatcher, findHostInstanceByFiber: function(n) {
    return n = wt(n), n === null ? null : n.stateNode;
  }, findFiberByHostInstance: gc.findFiberByHostInstance || ym, findHostInstancesForRefresh: null, scheduleRefresh: null, scheduleRoot: null, setRefreshHandler: null, getCurrentFiber: null, reconcilerVersion: "18.3.1-next-f1338f8080-20240426" };
  if (typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u") {
    var Sc = __REACT_DEVTOOLS_GLOBAL_HOOK__;
    if (!Sc.isDisabled && Sc.supportsFiber) try {
      No = Sc.inject(Kg), sa = Sc;
    } catch {
    }
  }
  return si.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = Sm, si.createPortal = function(n, r) {
    var o = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null;
    if (!Bp(r)) throw Error(v(200));
    return vm(n, r, null, o);
  }, si.createRoot = function(n, r) {
    if (!Bp(n)) throw Error(v(299));
    var o = !1, s = "", d = Vp;
    return r != null && (r.unstable_strictMode === !0 && (o = !0), r.identifierPrefix !== void 0 && (s = r.identifierPrefix), r.onRecoverableError !== void 0 && (d = r.onRecoverableError)), r = Gf(n, 1, !1, null, null, o, !1, s, d), n[vo] = r.current, $s(n.nodeType === 8 ? n.parentNode : n), new rl(r);
  }, si.findDOMNode = function(n) {
    if (n == null) return null;
    if (n.nodeType === 1) return n;
    var r = n._reactInternals;
    if (r === void 0)
      throw typeof n.render == "function" ? Error(v(188)) : (n = Object.keys(n).join(","), Error(v(268, n)));
    return n = wt(r), n = n === null ? null : n.stateNode, n;
  }, si.flushSync = function(n) {
    return Kl(n);
  }, si.hydrate = function(n, r, o) {
    if (!Jf(r)) throw Error(v(200));
    return Zf(null, n, r, !0, o);
  }, si.hydrateRoot = function(n, r, o) {
    if (!Bp(n)) throw Error(v(405));
    var s = o != null && o.hydratedSources || null, d = !1, h = "", b = Vp;
    if (o != null && (o.unstable_strictMode === !0 && (d = !0), o.identifierPrefix !== void 0 && (h = o.identifierPrefix), o.onRecoverableError !== void 0 && (b = o.onRecoverableError)), r = Hp(r, null, n, 1, o ?? null, d, !1, h, b), n[vo] = r.current, $s(n), s) for (n = 0; n < s.length; n++) o = s[n], d = o._getVersion, d = d(o._source), r.mutableSourceEagerHydrationData == null ? r.mutableSourceEagerHydrationData = [o, d] : r.mutableSourceEagerHydrationData.push(
      o,
      d
    );
    return new Xf(r);
  }, si.render = function(n, r, o) {
    if (!Jf(r)) throw Error(v(200));
    return Zf(null, n, r, !1, o);
  }, si.unmountComponentAtNode = function(n) {
    if (!Jf(n)) throw Error(v(40));
    return n._reactRootContainer ? (Kl(function() {
      Zf(null, null, n, !1, function() {
        n._reactRootContainer = null, n[vo] = null;
      });
    }), !0) : !1;
  }, si.unstable_batchedUpdates = Bf, si.unstable_renderSubtreeIntoContainer = function(n, r, o, s) {
    if (!Jf(o)) throw Error(v(200));
    if (n == null || n._reactInternals === void 0) throw Error(v(38));
    return Zf(n, r, o, !1, s);
  }, si.version = "18.3.1-next-f1338f8080-20240426", si;
}
var ci = {}, hR;
function DN() {
  if (hR) return ci;
  hR = 1;
  var u = {};
  /**
   * @license React
   * react-dom.development.js
   *
   * Copyright (c) Facebook, Inc. and its affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   */
  return u.NODE_ENV !== "production" && function() {
    typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u" && typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart == "function" && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart(new Error());
    var f = Vt, v = tw(), y = f.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED, S = !1;
    function T(e) {
      S = e;
    }
    function _(e) {
      if (!S) {
        for (var t = arguments.length, a = new Array(t > 1 ? t - 1 : 0), i = 1; i < t; i++)
          a[i - 1] = arguments[i];
        L("warn", e, a);
      }
    }
    function g(e) {
      if (!S) {
        for (var t = arguments.length, a = new Array(t > 1 ? t - 1 : 0), i = 1; i < t; i++)
          a[i - 1] = arguments[i];
        L("error", e, a);
      }
    }
    function L(e, t, a) {
      {
        var i = y.ReactDebugCurrentFrame, l = i.getStackAddendum();
        l !== "" && (t += "%s", a = a.concat([l]));
        var c = a.map(function(p) {
          return String(p);
        });
        c.unshift("Warning: " + t), Function.prototype.apply.call(console[e], console, c);
      }
    }
    var z = 0, A = 1, F = 2, U = 3, te = 4, B = 5, M = 6, j = 7, ce = 8, De = 9, de = 10, ue = 11, q = 12, se = 13, Ce = 14, Ge = 15, _t = 16, x = 17, ge = 18, je = 19, Qe = 21, Pe = 22, pt = 23, vt = 24, ot = 25, ie = !0, Ie = !1, ke = !1, k = !1, I = !1, ye = !0, Re = !0, be = !0, Le = !0, ze = /* @__PURE__ */ new Set(), we = {}, Ye = {};
    function et(e, t) {
      ut(e, t), ut(e + "Capture", t);
    }
    function ut(e, t) {
      we[e] && g("EventRegistry: More than one plugin attempted to publish the same registration name, `%s`.", e), we[e] = t;
      {
        var a = e.toLowerCase();
        Ye[a] = e, e === "onDoubleClick" && (Ye.ondblclick = e);
      }
      for (var i = 0; i < t.length; i++)
        ze.add(t[i]);
    }
    var Ht = typeof window < "u" && typeof window.document < "u" && typeof window.document.createElement < "u", Te = Object.prototype.hasOwnProperty;
    function Wt(e) {
      {
        var t = typeof Symbol == "function" && Symbol.toStringTag, a = t && e[Symbol.toStringTag] || e.constructor.name || "Object";
        return a;
      }
    }
    function Fn(e) {
      try {
        return Ln(e), !1;
      } catch {
        return !0;
      }
    }
    function Ln(e) {
      return "" + e;
    }
    function Gn(e, t) {
      if (Fn(e))
        return g("The provided `%s` attribute is an unsupported type %s. This value must be coerced to a string before before using it here.", t, Wt(e)), Ln(e);
    }
    function _a(e) {
      if (Fn(e))
        return g("The provided key is an unsupported type %s. This value must be coerced to a string before before using it here.", Wt(e)), Ln(e);
    }
    function di(e, t) {
      if (Fn(e))
        return g("The provided `%s` prop is an unsupported type %s. This value must be coerced to a string before before using it here.", t, Wt(e)), Ln(e);
    }
    function Ir(e, t) {
      if (Fn(e))
        return g("The provided `%s` CSS property is an unsupported type %s. This value must be coerced to a string before before using it here.", t, Wt(e)), Ln(e);
    }
    function ir(e) {
      if (Fn(e))
        return g("The provided HTML markup uses a value of unsupported type %s. This value must be coerced to a string before before using it here.", Wt(e)), Ln(e);
    }
    function dr(e) {
      if (Fn(e))
        return g("Form field values (value, checked, defaultValue, or defaultChecked props) must be strings, not %s. This value must be coerced to a string before before using it here.", Wt(e)), Ln(e);
    }
    var pr = 0, Pr = 1, pi = 2, Qn = 3, br = 4, la = 5, eo = 6, ka = ":A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD", xe = ka + "\\-.0-9\\u00B7\\u0300-\\u036F\\u203F-\\u2040", it = new RegExp("^[" + ka + "][" + xe + "]*$"), Rt = {}, Gt = {};
    function bn(e) {
      return Te.call(Gt, e) ? !0 : Te.call(Rt, e) ? !1 : it.test(e) ? (Gt[e] = !0, !0) : (Rt[e] = !0, g("Invalid attribute name: `%s`", e), !1);
    }
    function Tn(e, t, a) {
      return t !== null ? t.type === pr : a ? !1 : e.length > 2 && (e[0] === "o" || e[0] === "O") && (e[1] === "n" || e[1] === "N");
    }
    function Rn(e, t, a, i) {
      if (a !== null && a.type === pr)
        return !1;
      switch (typeof t) {
        case "function":
        case "symbol":
          return !0;
        case "boolean": {
          if (i)
            return !1;
          if (a !== null)
            return !a.acceptsBooleans;
          var l = e.toLowerCase().slice(0, 5);
          return l !== "data-" && l !== "aria-";
        }
        default:
          return !1;
      }
    }
    function vr(e, t, a, i) {
      if (t === null || typeof t > "u" || Rn(e, t, a, i))
        return !0;
      if (i)
        return !1;
      if (a !== null)
        switch (a.type) {
          case Qn:
            return !t;
          case br:
            return t === !1;
          case la:
            return isNaN(t);
          case eo:
            return isNaN(t) || t < 1;
        }
      return !1;
    }
    function gn(e) {
      return Qt.hasOwnProperty(e) ? Qt[e] : null;
    }
    function an(e, t, a, i, l, c, p) {
      this.acceptsBooleans = t === pi || t === Qn || t === br, this.attributeName = i, this.attributeNamespace = l, this.mustUseProperty = a, this.propertyName = e, this.type = t, this.sanitizeURL = c, this.removeEmptyString = p;
    }
    var Qt = {}, Oa = [
      "children",
      "dangerouslySetInnerHTML",
      // TODO: This prevents the assignment of defaultValue to regular
      // elements (not just inputs). Now that ReactDOMInput assigns to the
      // defaultValue property -- do we need this?
      "defaultValue",
      "defaultChecked",
      "innerHTML",
      "suppressContentEditableWarning",
      "suppressHydrationWarning",
      "style"
    ];
    Oa.forEach(function(e) {
      Qt[e] = new an(
        e,
        pr,
        !1,
        // mustUseProperty
        e,
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), [["acceptCharset", "accept-charset"], ["className", "class"], ["htmlFor", "for"], ["httpEquiv", "http-equiv"]].forEach(function(e) {
      var t = e[0], a = e[1];
      Qt[t] = new an(
        t,
        Pr,
        !1,
        // mustUseProperty
        a,
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), ["contentEditable", "draggable", "spellCheck", "value"].forEach(function(e) {
      Qt[e] = new an(
        e,
        pi,
        !1,
        // mustUseProperty
        e.toLowerCase(),
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), ["autoReverse", "externalResourcesRequired", "focusable", "preserveAlpha"].forEach(function(e) {
      Qt[e] = new an(
        e,
        pi,
        !1,
        // mustUseProperty
        e,
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), [
      "allowFullScreen",
      "async",
      // Note: there is a special case that prevents it from being written to the DOM
      // on the client side because the browsers are inconsistent. Instead we call focus().
      "autoFocus",
      "autoPlay",
      "controls",
      "default",
      "defer",
      "disabled",
      "disablePictureInPicture",
      "disableRemotePlayback",
      "formNoValidate",
      "hidden",
      "loop",
      "noModule",
      "noValidate",
      "open",
      "playsInline",
      "readOnly",
      "required",
      "reversed",
      "scoped",
      "seamless",
      // Microdata
      "itemScope"
    ].forEach(function(e) {
      Qt[e] = new an(
        e,
        Qn,
        !1,
        // mustUseProperty
        e.toLowerCase(),
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), [
      "checked",
      // Note: `option.selected` is not updated if `select.multiple` is
      // disabled with `removeAttribute`. We have special logic for handling this.
      "multiple",
      "muted",
      "selected"
      // NOTE: if you add a camelCased prop to this list,
      // you'll need to set attributeName to name.toLowerCase()
      // instead in the assignment below.
    ].forEach(function(e) {
      Qt[e] = new an(
        e,
        Qn,
        !0,
        // mustUseProperty
        e,
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), [
      "capture",
      "download"
      // NOTE: if you add a camelCased prop to this list,
      // you'll need to set attributeName to name.toLowerCase()
      // instead in the assignment below.
    ].forEach(function(e) {
      Qt[e] = new an(
        e,
        br,
        !1,
        // mustUseProperty
        e,
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), [
      "cols",
      "rows",
      "size",
      "span"
      // NOTE: if you add a camelCased prop to this list,
      // you'll need to set attributeName to name.toLowerCase()
      // instead in the assignment below.
    ].forEach(function(e) {
      Qt[e] = new an(
        e,
        eo,
        !1,
        // mustUseProperty
        e,
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), ["rowSpan", "start"].forEach(function(e) {
      Qt[e] = new an(
        e,
        la,
        !1,
        // mustUseProperty
        e.toLowerCase(),
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    });
    var Ia = /[\-\:]([a-z])/g, Ya = function(e) {
      return e[1].toUpperCase();
    };
    [
      "accent-height",
      "alignment-baseline",
      "arabic-form",
      "baseline-shift",
      "cap-height",
      "clip-path",
      "clip-rule",
      "color-interpolation",
      "color-interpolation-filters",
      "color-profile",
      "color-rendering",
      "dominant-baseline",
      "enable-background",
      "fill-opacity",
      "fill-rule",
      "flood-color",
      "flood-opacity",
      "font-family",
      "font-size",
      "font-size-adjust",
      "font-stretch",
      "font-style",
      "font-variant",
      "font-weight",
      "glyph-name",
      "glyph-orientation-horizontal",
      "glyph-orientation-vertical",
      "horiz-adv-x",
      "horiz-origin-x",
      "image-rendering",
      "letter-spacing",
      "lighting-color",
      "marker-end",
      "marker-mid",
      "marker-start",
      "overline-position",
      "overline-thickness",
      "paint-order",
      "panose-1",
      "pointer-events",
      "rendering-intent",
      "shape-rendering",
      "stop-color",
      "stop-opacity",
      "strikethrough-position",
      "strikethrough-thickness",
      "stroke-dasharray",
      "stroke-dashoffset",
      "stroke-linecap",
      "stroke-linejoin",
      "stroke-miterlimit",
      "stroke-opacity",
      "stroke-width",
      "text-anchor",
      "text-decoration",
      "text-rendering",
      "underline-position",
      "underline-thickness",
      "unicode-bidi",
      "unicode-range",
      "units-per-em",
      "v-alphabetic",
      "v-hanging",
      "v-ideographic",
      "v-mathematical",
      "vector-effect",
      "vert-adv-y",
      "vert-origin-x",
      "vert-origin-y",
      "word-spacing",
      "writing-mode",
      "xmlns:xlink",
      "x-height"
      // NOTE: if you add a camelCased prop to this list,
      // you'll need to set attributeName to name.toLowerCase()
      // instead in the assignment below.
    ].forEach(function(e) {
      var t = e.replace(Ia, Ya);
      Qt[t] = new an(
        t,
        Pr,
        !1,
        // mustUseProperty
        e,
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    }), [
      "xlink:actuate",
      "xlink:arcrole",
      "xlink:role",
      "xlink:show",
      "xlink:title",
      "xlink:type"
      // NOTE: if you add a camelCased prop to this list,
      // you'll need to set attributeName to name.toLowerCase()
      // instead in the assignment below.
    ].forEach(function(e) {
      var t = e.replace(Ia, Ya);
      Qt[t] = new an(
        t,
        Pr,
        !1,
        // mustUseProperty
        e,
        "http://www.w3.org/1999/xlink",
        !1,
        // sanitizeURL
        !1
      );
    }), [
      "xml:base",
      "xml:lang",
      "xml:space"
      // NOTE: if you add a camelCased prop to this list,
      // you'll need to set attributeName to name.toLowerCase()
      // instead in the assignment below.
    ].forEach(function(e) {
      var t = e.replace(Ia, Ya);
      Qt[t] = new an(
        t,
        Pr,
        !1,
        // mustUseProperty
        e,
        "http://www.w3.org/XML/1998/namespace",
        !1,
        // sanitizeURL
        !1
      );
    }), ["tabIndex", "crossOrigin"].forEach(function(e) {
      Qt[e] = new an(
        e,
        Pr,
        !1,
        // mustUseProperty
        e.toLowerCase(),
        // attributeName
        null,
        // attributeNamespace
        !1,
        // sanitizeURL
        !1
      );
    });
    var to = "xlinkHref";
    Qt[to] = new an(
      "xlinkHref",
      Pr,
      !1,
      // mustUseProperty
      "xlink:href",
      "http://www.w3.org/1999/xlink",
      !0,
      // sanitizeURL
      !1
    ), ["src", "href", "action", "formAction"].forEach(function(e) {
      Qt[e] = new an(
        e,
        Pr,
        !1,
        // mustUseProperty
        e.toLowerCase(),
        // attributeName
        null,
        // attributeNamespace
        !0,
        // sanitizeURL
        !0
      );
    });
    var Sl = /^[\u0000-\u001F ]*j[\r\n\t]*a[\r\n\t]*v[\r\n\t]*a[\r\n\t]*s[\r\n\t]*c[\r\n\t]*r[\r\n\t]*i[\r\n\t]*p[\r\n\t]*t[\r\n\t]*\:/i, El = !1;
    function no(e) {
      !El && Sl.test(e) && (El = !0, g("A future version of React will block javascript: URLs as a security precaution. Use event handlers instead if you can. If you need to generate unsafe HTML try using dangerouslySetInnerHTML instead. React was passed %s.", JSON.stringify(e)));
    }
    function Cl(e, t, a, i) {
      if (i.mustUseProperty) {
        var l = i.propertyName;
        return e[l];
      } else {
        Gn(a, t), i.sanitizeURL && no("" + a);
        var c = i.attributeName, p = null;
        if (i.type === br) {
          if (e.hasAttribute(c)) {
            var m = e.getAttribute(c);
            return m === "" ? !0 : vr(t, a, i, !1) ? m : m === "" + a ? a : m;
          }
        } else if (e.hasAttribute(c)) {
          if (vr(t, a, i, !1))
            return e.getAttribute(c);
          if (i.type === Qn)
            return a;
          p = e.getAttribute(c);
        }
        return vr(t, a, i, !1) ? p === null ? a : p : p === "" + a ? a : p;
      }
    }
    function Di(e, t, a, i) {
      {
        if (!bn(t))
          return;
        if (!e.hasAttribute(t))
          return a === void 0 ? void 0 : null;
        var l = e.getAttribute(t);
        return Gn(a, t), l === "" + a ? a : l;
      }
    }
    function Da(e, t, a, i) {
      var l = gn(t);
      if (!Tn(t, l, i)) {
        if (vr(t, a, l, i) && (a = null), i || l === null) {
          if (bn(t)) {
            var c = t;
            a === null ? e.removeAttribute(c) : (Gn(a, t), e.setAttribute(c, "" + a));
          }
          return;
        }
        var p = l.mustUseProperty;
        if (p) {
          var m = l.propertyName;
          if (a === null) {
            var E = l.type;
            e[m] = E === Qn ? !1 : "";
          } else
            e[m] = a;
          return;
        }
        var R = l.attributeName, w = l.attributeNamespace;
        if (a === null)
          e.removeAttribute(R);
        else {
          var V = l.type, $;
          V === Qn || V === br && a === !0 ? $ = "" : (Gn(a, R), $ = "" + a, l.sanitizeURL && no($.toString())), w ? e.setAttributeNS(w, R, $) : e.setAttribute(R, $);
        }
      }
    }
    var Tr = Symbol.for("react.element"), Na = Symbol.for("react.portal"), ua = Symbol.for("react.fragment"), Ni = Symbol.for("react.strict_mode"), Ai = Symbol.for("react.profiler"), ro = Symbol.for("react.provider"), N = Symbol.for("react.context"), fe = Symbol.for("react.forward_ref"), Ae = Symbol.for("react.suspense"), Ue = Symbol.for("react.suspense_list"), kt = Symbol.for("react.memo"), yt = Symbol.for("react.lazy"), Nt = Symbol.for("react.scope"), wt = Symbol.for("react.debug_trace_mode"), jn = Symbol.for("react.offscreen"), Sn = Symbol.for("react.legacy_hidden"), wn = Symbol.for("react.cache"), $r = Symbol.for("react.tracing_marker"), vi = Symbol.iterator, qt = "@@iterator";
    function Dn(e) {
      if (e === null || typeof e != "object")
        return null;
      var t = vi && e[vi] || e[qt];
      return typeof t == "function" ? t : null;
    }
    var Et = Object.assign, Mi = 0, ao, jc, io, No, sa, Cs, Yr;
    function bs() {
    }
    bs.__reactDisabledLog = !0;
    function Hc() {
      {
        if (Mi === 0) {
          ao = console.log, jc = console.info, io = console.warn, No = console.error, sa = console.group, Cs = console.groupCollapsed, Yr = console.groupEnd;
          var e = {
            configurable: !0,
            enumerable: !0,
            value: bs,
            writable: !0
          };
          Object.defineProperties(console, {
            info: e,
            log: e,
            warn: e,
            error: e,
            group: e,
            groupCollapsed: e,
            groupEnd: e
          });
        }
        Mi++;
      }
    }
    function Vc() {
      {
        if (Mi--, Mi === 0) {
          var e = {
            configurable: !0,
            enumerable: !0,
            writable: !0
          };
          Object.defineProperties(console, {
            log: Et({}, e, {
              value: ao
            }),
            info: Et({}, e, {
              value: jc
            }),
            warn: Et({}, e, {
              value: io
            }),
            error: Et({}, e, {
              value: No
            }),
            group: Et({}, e, {
              value: sa
            }),
            groupCollapsed: Et({}, e, {
              value: Cs
            }),
            groupEnd: Et({}, e, {
              value: Yr
            })
          });
        }
        Mi < 0 && g("disabledDepth fell below zero. This is a bug in React. Please file an issue.");
      }
    }
    var oo = y.ReactCurrentDispatcher, Ao;
    function ca(e, t, a) {
      {
        if (Ao === void 0)
          try {
            throw Error();
          } catch (l) {
            var i = l.stack.trim().match(/\n( *(at )?)/);
            Ao = i && i[1] || "";
          }
        return `
` + Ao + e;
      }
    }
    var Li = !1, Mo;
    {
      var hu = typeof WeakMap == "function" ? WeakMap : Map;
      Mo = new hu();
    }
    function lo(e, t) {
      if (!e || Li)
        return "";
      {
        var a = Mo.get(e);
        if (a !== void 0)
          return a;
      }
      var i;
      Li = !0;
      var l = Error.prepareStackTrace;
      Error.prepareStackTrace = void 0;
      var c;
      c = oo.current, oo.current = null, Hc();
      try {
        if (t) {
          var p = function() {
            throw Error();
          };
          if (Object.defineProperty(p.prototype, "props", {
            set: function() {
              throw Error();
            }
          }), typeof Reflect == "object" && Reflect.construct) {
            try {
              Reflect.construct(p, []);
            } catch (Z) {
              i = Z;
            }
            Reflect.construct(e, [], p);
          } else {
            try {
              p.call();
            } catch (Z) {
              i = Z;
            }
            e.call(p.prototype);
          }
        } else {
          try {
            throw Error();
          } catch (Z) {
            i = Z;
          }
          e();
        }
      } catch (Z) {
        if (Z && i && typeof Z.stack == "string") {
          for (var m = Z.stack.split(`
`), E = i.stack.split(`
`), R = m.length - 1, w = E.length - 1; R >= 1 && w >= 0 && m[R] !== E[w]; )
            w--;
          for (; R >= 1 && w >= 0; R--, w--)
            if (m[R] !== E[w]) {
              if (R !== 1 || w !== 1)
                do
                  if (R--, w--, w < 0 || m[R] !== E[w]) {
                    var V = `
` + m[R].replace(" at new ", " at ");
                    return e.displayName && V.includes("<anonymous>") && (V = V.replace("<anonymous>", e.displayName)), typeof e == "function" && Mo.set(e, V), V;
                  }
                while (R >= 1 && w >= 0);
              break;
            }
        }
      } finally {
        Li = !1, oo.current = c, Vc(), Error.prepareStackTrace = l;
      }
      var $ = e ? e.displayName || e.name : "", X = $ ? ca($) : "";
      return typeof e == "function" && Mo.set(e, X), X;
    }
    function bl(e, t, a) {
      return lo(e, !0);
    }
    function Tl(e, t, a) {
      return lo(e, !1);
    }
    function Lo(e) {
      var t = e.prototype;
      return !!(t && t.isReactComponent);
    }
    function Ts(e, t, a) {
      if (e == null)
        return "";
      if (typeof e == "function")
        return lo(e, Lo(e));
      if (typeof e == "string")
        return ca(e);
      switch (e) {
        case Ae:
          return ca("Suspense");
        case Ue:
          return ca("SuspenseList");
      }
      if (typeof e == "object")
        switch (e.$$typeof) {
          case fe:
            return Tl(e.render);
          case kt:
            return Ts(e.type, t, a);
          case yt: {
            var i = e, l = i._payload, c = i._init;
            try {
              return Ts(c(l), t, a);
            } catch {
            }
          }
        }
      return "";
    }
    function Rs(e) {
      switch (e._debugOwner && e._debugOwner.type, e._debugSource, e.tag) {
        case B:
          return ca(e.type);
        case _t:
          return ca("Lazy");
        case se:
          return ca("Suspense");
        case je:
          return ca("SuspenseList");
        case z:
        case F:
        case Ge:
          return Tl(e.type);
        case ue:
          return Tl(e.type.render);
        case A:
          return bl(e.type);
        default:
          return "";
      }
    }
    function Pt(e) {
      try {
        var t = "", a = e;
        do
          t += Rs(a), a = a.return;
        while (a);
        return t;
      } catch (i) {
        return `
Error generating stack: ` + i.message + `
` + i.stack;
      }
    }
    function ws(e, t, a) {
      var i = e.displayName;
      if (i)
        return i;
      var l = t.displayName || t.name || "";
      return l !== "" ? a + "(" + l + ")" : a;
    }
    function mu(e) {
      return e.displayName || "Context";
    }
    function $t(e) {
      if (e == null)
        return null;
      if (typeof e.tag == "number" && g("Received an unexpected object in getComponentNameFromType(). This is likely a bug in React. Please file an issue."), typeof e == "function")
        return e.displayName || e.name || null;
      if (typeof e == "string")
        return e;
      switch (e) {
        case ua:
          return "Fragment";
        case Na:
          return "Portal";
        case Ai:
          return "Profiler";
        case Ni:
          return "StrictMode";
        case Ae:
          return "Suspense";
        case Ue:
          return "SuspenseList";
      }
      if (typeof e == "object")
        switch (e.$$typeof) {
          case N:
            var t = e;
            return mu(t) + ".Consumer";
          case ro:
            var a = e;
            return mu(a._context) + ".Provider";
          case fe:
            return ws(e, e.render, "ForwardRef");
          case kt:
            var i = e.displayName || null;
            return i !== null ? i : $t(e.type) || "Memo";
          case yt: {
            var l = e, c = l._payload, p = l._init;
            try {
              return $t(p(c));
            } catch {
              return null;
            }
          }
        }
      return null;
    }
    function Bc(e, t, a) {
      var i = t.displayName || t.name || "";
      return e.displayName || (i !== "" ? a + "(" + i + ")" : a);
    }
    function zi(e) {
      return e.displayName || "Context";
    }
    function ht(e) {
      var t = e.tag, a = e.type;
      switch (t) {
        case vt:
          return "Cache";
        case De:
          var i = a;
          return zi(i) + ".Consumer";
        case de:
          var l = a;
          return zi(l._context) + ".Provider";
        case ge:
          return "DehydratedFragment";
        case ue:
          return Bc(a, a.render, "ForwardRef");
        case j:
          return "Fragment";
        case B:
          return a;
        case te:
          return "Portal";
        case U:
          return "Root";
        case M:
          return "Text";
        case _t:
          return $t(a);
        case ce:
          return a === Ni ? "StrictMode" : "Mode";
        case Pe:
          return "Offscreen";
        case q:
          return "Profiler";
        case Qe:
          return "Scope";
        case se:
          return "Suspense";
        case je:
          return "SuspenseList";
        case ot:
          return "TracingMarker";
        case A:
        case z:
        case x:
        case F:
        case Ce:
        case Ge:
          if (typeof a == "function")
            return a.displayName || a.name || null;
          if (typeof a == "string")
            return a;
          break;
      }
      return null;
    }
    var Rl = y.ReactDebugCurrentFrame, hr = null, fa = !1;
    function Wr() {
      {
        if (hr === null)
          return null;
        var e = hr._debugOwner;
        if (e !== null && typeof e < "u")
          return ht(e);
      }
      return null;
    }
    function Ui() {
      return hr === null ? "" : Pt(hr);
    }
    function zn() {
      Rl.getCurrentStack = null, hr = null, fa = !1;
    }
    function on(e) {
      Rl.getCurrentStack = e === null ? null : Ui, hr = e, fa = !1;
    }
    function hi() {
      return hr;
    }
    function Wa(e) {
      fa = e;
    }
    function Fr(e) {
      return "" + e;
    }
    function Gr(e) {
      switch (typeof e) {
        case "boolean":
        case "number":
        case "string":
        case "undefined":
          return e;
        case "object":
          return dr(e), e;
        default:
          return "";
      }
    }
    var Vd = {
      button: !0,
      checkbox: !0,
      image: !0,
      hidden: !0,
      radio: !0,
      reset: !0,
      submit: !0
    };
    function yu(e, t) {
      Vd[t.type] || t.onChange || t.onInput || t.readOnly || t.disabled || t.value == null || g("You provided a `value` prop to a form field without an `onChange` handler. This will render a read-only field. If the field should be mutable use `defaultValue`. Otherwise, set either `onChange` or `readOnly`."), t.onChange || t.readOnly || t.disabled || t.checked == null || g("You provided a `checked` prop to a form field without an `onChange` handler. This will render a read-only field. If the field should be mutable use `defaultChecked`. Otherwise, set either `onChange` or `readOnly`.");
    }
    function wl(e) {
      var t = e.type, a = e.nodeName;
      return a && a.toLowerCase() === "input" && (t === "checkbox" || t === "radio");
    }
    function gu(e) {
      return e._valueTracker;
    }
    function Su(e) {
      e._valueTracker = null;
    }
    function xl(e) {
      var t = "";
      return e && (wl(e) ? t = e.checked ? "true" : "false" : t = e.value), t;
    }
    function Ga(e) {
      var t = wl(e) ? "checked" : "value", a = Object.getOwnPropertyDescriptor(e.constructor.prototype, t);
      dr(e[t]);
      var i = "" + e[t];
      if (!(e.hasOwnProperty(t) || typeof a > "u" || typeof a.get != "function" || typeof a.set != "function")) {
        var l = a.get, c = a.set;
        Object.defineProperty(e, t, {
          configurable: !0,
          get: function() {
            return l.call(this);
          },
          set: function(m) {
            dr(m), i = "" + m, c.call(this, m);
          }
        }), Object.defineProperty(e, t, {
          enumerable: a.enumerable
        });
        var p = {
          getValue: function() {
            return i;
          },
          setValue: function(m) {
            dr(m), i = "" + m;
          },
          stopTracking: function() {
            Su(e), delete e[t];
          }
        };
        return p;
      }
    }
    function Qa(e) {
      gu(e) || (e._valueTracker = Ga(e));
    }
    function zo(e) {
      if (!e)
        return !1;
      var t = gu(e);
      if (!t)
        return !0;
      var a = t.getValue(), i = xl(e);
      return i !== a ? (t.setValue(i), !0) : !1;
    }
    function uo(e) {
      if (e = e || (typeof document < "u" ? document : void 0), typeof e > "u")
        return null;
      try {
        return e.activeElement || e.body;
      } catch {
        return e.body;
      }
    }
    var Eu = !1, Uo = !1, so = !1, Cu = !1;
    function xs(e) {
      var t = e.type === "checkbox" || e.type === "radio";
      return t ? e.checked != null : e.value != null;
    }
    function qa(e, t) {
      var a = e, i = t.checked, l = Et({}, t, {
        defaultChecked: void 0,
        defaultValue: void 0,
        value: void 0,
        checked: i ?? a._wrapperState.initialChecked
      });
      return l;
    }
    function bu(e, t) {
      yu("input", t), t.checked !== void 0 && t.defaultChecked !== void 0 && !Uo && (g("%s contains an input of type %s with both checked and defaultChecked props. Input elements must be either controlled or uncontrolled (specify either the checked prop, or the defaultChecked prop, but not both). Decide between using a controlled or uncontrolled input element and remove one of these props. More info: https://reactjs.org/link/controlled-components", Wr() || "A component", t.type), Uo = !0), t.value !== void 0 && t.defaultValue !== void 0 && !Eu && (g("%s contains an input of type %s with both value and defaultValue props. Input elements must be either controlled or uncontrolled (specify either the value prop, or the defaultValue prop, but not both). Decide between using a controlled or uncontrolled input element and remove one of these props. More info: https://reactjs.org/link/controlled-components", Wr() || "A component", t.type), Eu = !0);
      var a = e, i = t.defaultValue == null ? "" : t.defaultValue;
      a._wrapperState = {
        initialChecked: t.checked != null ? t.checked : t.defaultChecked,
        initialValue: Gr(t.value != null ? t.value : i),
        controlled: xs(t)
      };
    }
    function C(e, t) {
      var a = e, i = t.checked;
      i != null && Da(a, "checked", i, !1);
    }
    function D(e, t) {
      var a = e;
      {
        var i = xs(t);
        !a._wrapperState.controlled && i && !Cu && (g("A component is changing an uncontrolled input to be controlled. This is likely caused by the value changing from undefined to a defined value, which should not happen. Decide between using a controlled or uncontrolled input element for the lifetime of the component. More info: https://reactjs.org/link/controlled-components"), Cu = !0), a._wrapperState.controlled && !i && !so && (g("A component is changing a controlled input to be uncontrolled. This is likely caused by the value changing from a defined to undefined, which should not happen. Decide between using a controlled or uncontrolled input element for the lifetime of the component. More info: https://reactjs.org/link/controlled-components"), so = !0);
      }
      C(e, t);
      var l = Gr(t.value), c = t.type;
      if (l != null)
        c === "number" ? (l === 0 && a.value === "" || // We explicitly want to coerce to number here if possible.
        // eslint-disable-next-line
        a.value != l) && (a.value = Fr(l)) : a.value !== Fr(l) && (a.value = Fr(l));
      else if (c === "submit" || c === "reset") {
        a.removeAttribute("value");
        return;
      }
      t.hasOwnProperty("value") ? Ke(a, t.type, l) : t.hasOwnProperty("defaultValue") && Ke(a, t.type, Gr(t.defaultValue)), t.checked == null && t.defaultChecked != null && (a.defaultChecked = !!t.defaultChecked);
    }
    function K(e, t, a) {
      var i = e;
      if (t.hasOwnProperty("value") || t.hasOwnProperty("defaultValue")) {
        var l = t.type, c = l === "submit" || l === "reset";
        if (c && (t.value === void 0 || t.value === null))
          return;
        var p = Fr(i._wrapperState.initialValue);
        a || p !== i.value && (i.value = p), i.defaultValue = p;
      }
      var m = i.name;
      m !== "" && (i.name = ""), i.defaultChecked = !i.defaultChecked, i.defaultChecked = !!i._wrapperState.initialChecked, m !== "" && (i.name = m);
    }
    function ee(e, t) {
      var a = e;
      D(a, t), Ee(a, t);
    }
    function Ee(e, t) {
      var a = t.name;
      if (t.type === "radio" && a != null) {
        for (var i = e; i.parentNode; )
          i = i.parentNode;
        Gn(a, "name");
        for (var l = i.querySelectorAll("input[name=" + JSON.stringify("" + a) + '][type="radio"]'), c = 0; c < l.length; c++) {
          var p = l[c];
          if (!(p === e || p.form !== e.form)) {
            var m = Um(p);
            if (!m)
              throw new Error("ReactDOMInput: Mixing React and non-React radio inputs with the same `name` is not supported.");
            zo(p), D(p, m);
          }
        }
      }
    }
    function Ke(e, t, a) {
      // Focused number inputs synchronize on blur. See ChangeEventPlugin.js
      (t !== "number" || uo(e.ownerDocument) !== e) && (a == null ? e.defaultValue = Fr(e._wrapperState.initialValue) : e.defaultValue !== Fr(a) && (e.defaultValue = Fr(a)));
    }
    var He = !1, ft = !1, xt = !1;
    function Kt(e, t) {
      t.value == null && (typeof t.children == "object" && t.children !== null ? f.Children.forEach(t.children, function(a) {
        a != null && (typeof a == "string" || typeof a == "number" || ft || (ft = !0, g("Cannot infer the option value of complex children. Pass a `value` prop or use a plain string as children to <option>.")));
      }) : t.dangerouslySetInnerHTML != null && (xt || (xt = !0, g("Pass a `value` prop if you set dangerouslyInnerHTML so React knows which value should be selected.")))), t.selected != null && !He && (g("Use the `defaultValue` or `value` props on <select> instead of setting `selected` on <option>."), He = !0);
    }
    function ln(e, t) {
      t.value != null && e.setAttribute("value", Fr(Gr(t.value)));
    }
    var un = Array.isArray;
    function bt(e) {
      return un(e);
    }
    var hn;
    hn = !1;
    function Hn() {
      var e = Wr();
      return e ? `

Check the render method of \`` + e + "`." : "";
    }
    var _l = ["value", "defaultValue"];
    function _s(e) {
      {
        yu("select", e);
        for (var t = 0; t < _l.length; t++) {
          var a = _l[t];
          if (e[a] != null) {
            var i = bt(e[a]);
            e.multiple && !i ? g("The `%s` prop supplied to <select> must be an array if `multiple` is true.%s", a, Hn()) : !e.multiple && i && g("The `%s` prop supplied to <select> must be a scalar value if `multiple` is false.%s", a, Hn());
          }
        }
      }
    }
    function co(e, t, a, i) {
      var l = e.options;
      if (t) {
        for (var c = a, p = {}, m = 0; m < c.length; m++)
          p["$" + c[m]] = !0;
        for (var E = 0; E < l.length; E++) {
          var R = p.hasOwnProperty("$" + l[E].value);
          l[E].selected !== R && (l[E].selected = R), R && i && (l[E].defaultSelected = !0);
        }
      } else {
        for (var w = Fr(Gr(a)), V = null, $ = 0; $ < l.length; $++) {
          if (l[$].value === w) {
            l[$].selected = !0, i && (l[$].defaultSelected = !0);
            return;
          }
          V === null && !l[$].disabled && (V = l[$]);
        }
        V !== null && (V.selected = !0);
      }
    }
    function kl(e, t) {
      return Et({}, t, {
        value: void 0
      });
    }
    function ks(e, t) {
      var a = e;
      _s(t), a._wrapperState = {
        wasMultiple: !!t.multiple
      }, t.value !== void 0 && t.defaultValue !== void 0 && !hn && (g("Select elements must be either controlled or uncontrolled (specify either the value prop, or the defaultValue prop, but not both). Decide between using a controlled or uncontrolled select element and remove one of these props. More info: https://reactjs.org/link/controlled-components"), hn = !0);
    }
    function Bd(e, t) {
      var a = e;
      a.multiple = !!t.multiple;
      var i = t.value;
      i != null ? co(a, !!t.multiple, i, !1) : t.defaultValue != null && co(a, !!t.multiple, t.defaultValue, !0);
    }
    function Ic(e, t) {
      var a = e, i = a._wrapperState.wasMultiple;
      a._wrapperState.wasMultiple = !!t.multiple;
      var l = t.value;
      l != null ? co(a, !!t.multiple, l, !1) : i !== !!t.multiple && (t.defaultValue != null ? co(a, !!t.multiple, t.defaultValue, !0) : co(a, !!t.multiple, t.multiple ? [] : "", !1));
    }
    function Id(e, t) {
      var a = e, i = t.value;
      i != null && co(a, !!t.multiple, i, !1);
    }
    var ih = !1;
    function Yc(e, t) {
      var a = e;
      if (t.dangerouslySetInnerHTML != null)
        throw new Error("`dangerouslySetInnerHTML` does not make sense on <textarea>.");
      var i = Et({}, t, {
        value: void 0,
        defaultValue: void 0,
        children: Fr(a._wrapperState.initialValue)
      });
      return i;
    }
    function oh(e, t) {
      var a = e;
      yu("textarea", t), t.value !== void 0 && t.defaultValue !== void 0 && !ih && (g("%s contains a textarea with both value and defaultValue props. Textarea elements must be either controlled or uncontrolled (specify either the value prop, or the defaultValue prop, but not both). Decide between using a controlled or uncontrolled textarea and remove one of these props. More info: https://reactjs.org/link/controlled-components", Wr() || "A component"), ih = !0);
      var i = t.value;
      if (i == null) {
        var l = t.children, c = t.defaultValue;
        if (l != null) {
          g("Use the `defaultValue` or `value` props instead of setting children on <textarea>.");
          {
            if (c != null)
              throw new Error("If you supply `defaultValue` on a <textarea>, do not pass children.");
            if (bt(l)) {
              if (l.length > 1)
                throw new Error("<textarea> can only have at most one child.");
              l = l[0];
            }
            c = l;
          }
        }
        c == null && (c = ""), i = c;
      }
      a._wrapperState = {
        initialValue: Gr(i)
      };
    }
    function lh(e, t) {
      var a = e, i = Gr(t.value), l = Gr(t.defaultValue);
      if (i != null) {
        var c = Fr(i);
        c !== a.value && (a.value = c), t.defaultValue == null && a.defaultValue !== c && (a.defaultValue = c);
      }
      l != null && (a.defaultValue = Fr(l));
    }
    function uh(e, t) {
      var a = e, i = a.textContent;
      i === a._wrapperState.initialValue && i !== "" && i !== null && (a.value = i);
    }
    function wg(e, t) {
      lh(e, t);
    }
    var mi = "http://www.w3.org/1999/xhtml", xg = "http://www.w3.org/1998/Math/MathML", Yd = "http://www.w3.org/2000/svg";
    function Wd(e) {
      switch (e) {
        case "svg":
          return Yd;
        case "math":
          return xg;
        default:
          return mi;
      }
    }
    function Wc(e, t) {
      return e == null || e === mi ? Wd(t) : e === Yd && t === "foreignObject" ? mi : e;
    }
    var _g = function(e) {
      return typeof MSApp < "u" && MSApp.execUnsafeLocalFunction ? function(t, a, i, l) {
        MSApp.execUnsafeLocalFunction(function() {
          return e(t, a, i, l);
        });
      } : e;
    }, Gc, sh = _g(function(e, t) {
      if (e.namespaceURI === Yd && !("innerHTML" in e)) {
        Gc = Gc || document.createElement("div"), Gc.innerHTML = "<svg>" + t.valueOf().toString() + "</svg>";
        for (var a = Gc.firstChild; e.firstChild; )
          e.removeChild(e.firstChild);
        for (; a.firstChild; )
          e.appendChild(a.firstChild);
        return;
      }
      e.innerHTML = t;
    }), da = 1, fo = 3, qn = 8, po = 9, Os = 11, Po = function(e, t) {
      if (t) {
        var a = e.firstChild;
        if (a && a === e.lastChild && a.nodeType === fo) {
          a.nodeValue = t;
          return;
        }
      }
      e.textContent = t;
    }, kg = {
      animation: ["animationDelay", "animationDirection", "animationDuration", "animationFillMode", "animationIterationCount", "animationName", "animationPlayState", "animationTimingFunction"],
      background: ["backgroundAttachment", "backgroundClip", "backgroundColor", "backgroundImage", "backgroundOrigin", "backgroundPositionX", "backgroundPositionY", "backgroundRepeat", "backgroundSize"],
      backgroundPosition: ["backgroundPositionX", "backgroundPositionY"],
      border: ["borderBottomColor", "borderBottomStyle", "borderBottomWidth", "borderImageOutset", "borderImageRepeat", "borderImageSlice", "borderImageSource", "borderImageWidth", "borderLeftColor", "borderLeftStyle", "borderLeftWidth", "borderRightColor", "borderRightStyle", "borderRightWidth", "borderTopColor", "borderTopStyle", "borderTopWidth"],
      borderBlockEnd: ["borderBlockEndColor", "borderBlockEndStyle", "borderBlockEndWidth"],
      borderBlockStart: ["borderBlockStartColor", "borderBlockStartStyle", "borderBlockStartWidth"],
      borderBottom: ["borderBottomColor", "borderBottomStyle", "borderBottomWidth"],
      borderColor: ["borderBottomColor", "borderLeftColor", "borderRightColor", "borderTopColor"],
      borderImage: ["borderImageOutset", "borderImageRepeat", "borderImageSlice", "borderImageSource", "borderImageWidth"],
      borderInlineEnd: ["borderInlineEndColor", "borderInlineEndStyle", "borderInlineEndWidth"],
      borderInlineStart: ["borderInlineStartColor", "borderInlineStartStyle", "borderInlineStartWidth"],
      borderLeft: ["borderLeftColor", "borderLeftStyle", "borderLeftWidth"],
      borderRadius: ["borderBottomLeftRadius", "borderBottomRightRadius", "borderTopLeftRadius", "borderTopRightRadius"],
      borderRight: ["borderRightColor", "borderRightStyle", "borderRightWidth"],
      borderStyle: ["borderBottomStyle", "borderLeftStyle", "borderRightStyle", "borderTopStyle"],
      borderTop: ["borderTopColor", "borderTopStyle", "borderTopWidth"],
      borderWidth: ["borderBottomWidth", "borderLeftWidth", "borderRightWidth", "borderTopWidth"],
      columnRule: ["columnRuleColor", "columnRuleStyle", "columnRuleWidth"],
      columns: ["columnCount", "columnWidth"],
      flex: ["flexBasis", "flexGrow", "flexShrink"],
      flexFlow: ["flexDirection", "flexWrap"],
      font: ["fontFamily", "fontFeatureSettings", "fontKerning", "fontLanguageOverride", "fontSize", "fontSizeAdjust", "fontStretch", "fontStyle", "fontVariant", "fontVariantAlternates", "fontVariantCaps", "fontVariantEastAsian", "fontVariantLigatures", "fontVariantNumeric", "fontVariantPosition", "fontWeight", "lineHeight"],
      fontVariant: ["fontVariantAlternates", "fontVariantCaps", "fontVariantEastAsian", "fontVariantLigatures", "fontVariantNumeric", "fontVariantPosition"],
      gap: ["columnGap", "rowGap"],
      grid: ["gridAutoColumns", "gridAutoFlow", "gridAutoRows", "gridTemplateAreas", "gridTemplateColumns", "gridTemplateRows"],
      gridArea: ["gridColumnEnd", "gridColumnStart", "gridRowEnd", "gridRowStart"],
      gridColumn: ["gridColumnEnd", "gridColumnStart"],
      gridColumnGap: ["columnGap"],
      gridGap: ["columnGap", "rowGap"],
      gridRow: ["gridRowEnd", "gridRowStart"],
      gridRowGap: ["rowGap"],
      gridTemplate: ["gridTemplateAreas", "gridTemplateColumns", "gridTemplateRows"],
      listStyle: ["listStyleImage", "listStylePosition", "listStyleType"],
      margin: ["marginBottom", "marginLeft", "marginRight", "marginTop"],
      marker: ["markerEnd", "markerMid", "markerStart"],
      mask: ["maskClip", "maskComposite", "maskImage", "maskMode", "maskOrigin", "maskPositionX", "maskPositionY", "maskRepeat", "maskSize"],
      maskPosition: ["maskPositionX", "maskPositionY"],
      outline: ["outlineColor", "outlineStyle", "outlineWidth"],
      overflow: ["overflowX", "overflowY"],
      padding: ["paddingBottom", "paddingLeft", "paddingRight", "paddingTop"],
      placeContent: ["alignContent", "justifyContent"],
      placeItems: ["alignItems", "justifyItems"],
      placeSelf: ["alignSelf", "justifySelf"],
      textDecoration: ["textDecorationColor", "textDecorationLine", "textDecorationStyle"],
      textEmphasis: ["textEmphasisColor", "textEmphasisStyle"],
      transition: ["transitionDelay", "transitionDuration", "transitionProperty", "transitionTimingFunction"],
      wordWrap: ["overflowWrap"]
    }, Tu = {
      animationIterationCount: !0,
      aspectRatio: !0,
      borderImageOutset: !0,
      borderImageSlice: !0,
      borderImageWidth: !0,
      boxFlex: !0,
      boxFlexGroup: !0,
      boxOrdinalGroup: !0,
      columnCount: !0,
      columns: !0,
      flex: !0,
      flexGrow: !0,
      flexPositive: !0,
      flexShrink: !0,
      flexNegative: !0,
      flexOrder: !0,
      gridArea: !0,
      gridRow: !0,
      gridRowEnd: !0,
      gridRowSpan: !0,
      gridRowStart: !0,
      gridColumn: !0,
      gridColumnEnd: !0,
      gridColumnSpan: !0,
      gridColumnStart: !0,
      fontWeight: !0,
      lineClamp: !0,
      lineHeight: !0,
      opacity: !0,
      order: !0,
      orphans: !0,
      tabSize: !0,
      widows: !0,
      zIndex: !0,
      zoom: !0,
      // SVG-related properties
      fillOpacity: !0,
      floodOpacity: !0,
      stopOpacity: !0,
      strokeDasharray: !0,
      strokeDashoffset: !0,
      strokeMiterlimit: !0,
      strokeOpacity: !0,
      strokeWidth: !0
    };
    function ch(e, t) {
      return e + t.charAt(0).toUpperCase() + t.substring(1);
    }
    var fh = ["Webkit", "ms", "Moz", "O"];
    Object.keys(Tu).forEach(function(e) {
      fh.forEach(function(t) {
        Tu[ch(t, e)] = Tu[e];
      });
    });
    function Qc(e, t, a) {
      var i = t == null || typeof t == "boolean" || t === "";
      return i ? "" : !a && typeof t == "number" && t !== 0 && !(Tu.hasOwnProperty(e) && Tu[e]) ? t + "px" : (Ir(t, e), ("" + t).trim());
    }
    var dh = /([A-Z])/g, Ru = /^ms-/;
    function Og(e) {
      return e.replace(dh, "-$1").toLowerCase().replace(Ru, "-ms-");
    }
    var ph = function() {
    };
    {
      var Dg = /^(?:webkit|moz|o)[A-Z]/, vh = /^-ms-/, hh = /-(.)/g, wu = /;\s*$/, Pi = {}, Gd = {}, Ds = !1, mh = !1, yh = function(e) {
        return e.replace(hh, function(t, a) {
          return a.toUpperCase();
        });
      }, Qd = function(e) {
        Pi.hasOwnProperty(e) && Pi[e] || (Pi[e] = !0, g(
          "Unsupported style property %s. Did you mean %s?",
          e,
          // As Andi Smith suggests
          // (http://www.andismith.com/blog/2012/02/modernizr-prefixed/), an `-ms` prefix
          // is converted to lowercase `ms`.
          yh(e.replace(vh, "ms-"))
        ));
      }, qd = function(e) {
        Pi.hasOwnProperty(e) && Pi[e] || (Pi[e] = !0, g("Unsupported vendor-prefixed style property %s. Did you mean %s?", e, e.charAt(0).toUpperCase() + e.slice(1)));
      }, gh = function(e, t) {
        Gd.hasOwnProperty(t) && Gd[t] || (Gd[t] = !0, g(`Style property values shouldn't contain a semicolon. Try "%s: %s" instead.`, e, t.replace(wu, "")));
      }, Sh = function(e, t) {
        Ds || (Ds = !0, g("`NaN` is an invalid value for the `%s` css style property.", e));
      }, Eh = function(e, t) {
        mh || (mh = !0, g("`Infinity` is an invalid value for the `%s` css style property.", e));
      };
      ph = function(e, t) {
        e.indexOf("-") > -1 ? Qd(e) : Dg.test(e) ? qd(e) : wu.test(t) && gh(e, t), typeof t == "number" && (isNaN(t) ? Sh(e, t) : isFinite(t) || Eh(e, t));
      };
    }
    var Ng = ph;
    function Ag(e) {
      {
        var t = "", a = "";
        for (var i in e)
          if (e.hasOwnProperty(i)) {
            var l = e[i];
            if (l != null) {
              var c = i.indexOf("--") === 0;
              t += a + (c ? i : Og(i)) + ":", t += Qc(i, l, c), a = ";";
            }
          }
        return t || null;
      }
    }
    function Ch(e, t) {
      var a = e.style;
      for (var i in t)
        if (t.hasOwnProperty(i)) {
          var l = i.indexOf("--") === 0;
          l || Ng(i, t[i]);
          var c = Qc(i, t[i], l);
          i === "float" && (i = "cssFloat"), l ? a.setProperty(i, c) : a[i] = c;
        }
    }
    function Mg(e) {
      return e == null || typeof e == "boolean" || e === "";
    }
    function bh(e) {
      var t = {};
      for (var a in e)
        for (var i = kg[a] || [a], l = 0; l < i.length; l++)
          t[i[l]] = a;
      return t;
    }
    function yi(e, t) {
      {
        if (!t)
          return;
        var a = bh(e), i = bh(t), l = {};
        for (var c in a) {
          var p = a[c], m = i[c];
          if (m && p !== m) {
            var E = p + "," + m;
            if (l[E])
              continue;
            l[E] = !0, g("%s a style property during rerender (%s) when a conflicting property is set (%s) can lead to styling bugs. To avoid this, don't mix shorthand and non-shorthand properties for the same value; instead, replace the shorthand with separate values.", Mg(e[p]) ? "Removing" : "Updating", p, m);
          }
        }
      }
    }
    var Ns = {
      area: !0,
      base: !0,
      br: !0,
      col: !0,
      embed: !0,
      hr: !0,
      img: !0,
      input: !0,
      keygen: !0,
      link: !0,
      meta: !0,
      param: !0,
      source: !0,
      track: !0,
      wbr: !0
      // NOTE: menuitem's close tag should be omitted, but that causes problems.
    }, Th = Et({
      menuitem: !0
    }, Ns), Rh = "__html";
    function qc(e, t) {
      if (t) {
        if (Th[e] && (t.children != null || t.dangerouslySetInnerHTML != null))
          throw new Error(e + " is a void element tag and must neither have `children` nor use `dangerouslySetInnerHTML`.");
        if (t.dangerouslySetInnerHTML != null) {
          if (t.children != null)
            throw new Error("Can only set one of `children` or `props.dangerouslySetInnerHTML`.");
          if (typeof t.dangerouslySetInnerHTML != "object" || !(Rh in t.dangerouslySetInnerHTML))
            throw new Error("`props.dangerouslySetInnerHTML` must be in the form `{__html: ...}`. Please visit https://reactjs.org/link/dangerously-set-inner-html for more information.");
        }
        if (!t.suppressContentEditableWarning && t.contentEditable && t.children != null && g("A component is `contentEditable` and contains `children` managed by React. It is now your responsibility to guarantee that none of those nodes are unexpectedly modified or duplicated. This is probably not intentional."), t.style != null && typeof t.style != "object")
          throw new Error("The `style` prop expects a mapping from style properties to values, not a string. For example, style={{marginRight: spacing + 'em'}} when using JSX.");
      }
    }
    function $o(e, t) {
      if (e.indexOf("-") === -1)
        return typeof t.is == "string";
      switch (e) {
        case "annotation-xml":
        case "color-profile":
        case "font-face":
        case "font-face-src":
        case "font-face-uri":
        case "font-face-format":
        case "font-face-name":
        case "missing-glyph":
          return !1;
        default:
          return !0;
      }
    }
    var xu = {
      // HTML
      accept: "accept",
      acceptcharset: "acceptCharset",
      "accept-charset": "acceptCharset",
      accesskey: "accessKey",
      action: "action",
      allowfullscreen: "allowFullScreen",
      alt: "alt",
      as: "as",
      async: "async",
      autocapitalize: "autoCapitalize",
      autocomplete: "autoComplete",
      autocorrect: "autoCorrect",
      autofocus: "autoFocus",
      autoplay: "autoPlay",
      autosave: "autoSave",
      capture: "capture",
      cellpadding: "cellPadding",
      cellspacing: "cellSpacing",
      challenge: "challenge",
      charset: "charSet",
      checked: "checked",
      children: "children",
      cite: "cite",
      class: "className",
      classid: "classID",
      classname: "className",
      cols: "cols",
      colspan: "colSpan",
      content: "content",
      contenteditable: "contentEditable",
      contextmenu: "contextMenu",
      controls: "controls",
      controlslist: "controlsList",
      coords: "coords",
      crossorigin: "crossOrigin",
      dangerouslysetinnerhtml: "dangerouslySetInnerHTML",
      data: "data",
      datetime: "dateTime",
      default: "default",
      defaultchecked: "defaultChecked",
      defaultvalue: "defaultValue",
      defer: "defer",
      dir: "dir",
      disabled: "disabled",
      disablepictureinpicture: "disablePictureInPicture",
      disableremoteplayback: "disableRemotePlayback",
      download: "download",
      draggable: "draggable",
      enctype: "encType",
      enterkeyhint: "enterKeyHint",
      for: "htmlFor",
      form: "form",
      formmethod: "formMethod",
      formaction: "formAction",
      formenctype: "formEncType",
      formnovalidate: "formNoValidate",
      formtarget: "formTarget",
      frameborder: "frameBorder",
      headers: "headers",
      height: "height",
      hidden: "hidden",
      high: "high",
      href: "href",
      hreflang: "hrefLang",
      htmlfor: "htmlFor",
      httpequiv: "httpEquiv",
      "http-equiv": "httpEquiv",
      icon: "icon",
      id: "id",
      imagesizes: "imageSizes",
      imagesrcset: "imageSrcSet",
      innerhtml: "innerHTML",
      inputmode: "inputMode",
      integrity: "integrity",
      is: "is",
      itemid: "itemID",
      itemprop: "itemProp",
      itemref: "itemRef",
      itemscope: "itemScope",
      itemtype: "itemType",
      keyparams: "keyParams",
      keytype: "keyType",
      kind: "kind",
      label: "label",
      lang: "lang",
      list: "list",
      loop: "loop",
      low: "low",
      manifest: "manifest",
      marginwidth: "marginWidth",
      marginheight: "marginHeight",
      max: "max",
      maxlength: "maxLength",
      media: "media",
      mediagroup: "mediaGroup",
      method: "method",
      min: "min",
      minlength: "minLength",
      multiple: "multiple",
      muted: "muted",
      name: "name",
      nomodule: "noModule",
      nonce: "nonce",
      novalidate: "noValidate",
      open: "open",
      optimum: "optimum",
      pattern: "pattern",
      placeholder: "placeholder",
      playsinline: "playsInline",
      poster: "poster",
      preload: "preload",
      profile: "profile",
      radiogroup: "radioGroup",
      readonly: "readOnly",
      referrerpolicy: "referrerPolicy",
      rel: "rel",
      required: "required",
      reversed: "reversed",
      role: "role",
      rows: "rows",
      rowspan: "rowSpan",
      sandbox: "sandbox",
      scope: "scope",
      scoped: "scoped",
      scrolling: "scrolling",
      seamless: "seamless",
      selected: "selected",
      shape: "shape",
      size: "size",
      sizes: "sizes",
      span: "span",
      spellcheck: "spellCheck",
      src: "src",
      srcdoc: "srcDoc",
      srclang: "srcLang",
      srcset: "srcSet",
      start: "start",
      step: "step",
      style: "style",
      summary: "summary",
      tabindex: "tabIndex",
      target: "target",
      title: "title",
      type: "type",
      usemap: "useMap",
      value: "value",
      width: "width",
      wmode: "wmode",
      wrap: "wrap",
      // SVG
      about: "about",
      accentheight: "accentHeight",
      "accent-height": "accentHeight",
      accumulate: "accumulate",
      additive: "additive",
      alignmentbaseline: "alignmentBaseline",
      "alignment-baseline": "alignmentBaseline",
      allowreorder: "allowReorder",
      alphabetic: "alphabetic",
      amplitude: "amplitude",
      arabicform: "arabicForm",
      "arabic-form": "arabicForm",
      ascent: "ascent",
      attributename: "attributeName",
      attributetype: "attributeType",
      autoreverse: "autoReverse",
      azimuth: "azimuth",
      basefrequency: "baseFrequency",
      baselineshift: "baselineShift",
      "baseline-shift": "baselineShift",
      baseprofile: "baseProfile",
      bbox: "bbox",
      begin: "begin",
      bias: "bias",
      by: "by",
      calcmode: "calcMode",
      capheight: "capHeight",
      "cap-height": "capHeight",
      clip: "clip",
      clippath: "clipPath",
      "clip-path": "clipPath",
      clippathunits: "clipPathUnits",
      cliprule: "clipRule",
      "clip-rule": "clipRule",
      color: "color",
      colorinterpolation: "colorInterpolation",
      "color-interpolation": "colorInterpolation",
      colorinterpolationfilters: "colorInterpolationFilters",
      "color-interpolation-filters": "colorInterpolationFilters",
      colorprofile: "colorProfile",
      "color-profile": "colorProfile",
      colorrendering: "colorRendering",
      "color-rendering": "colorRendering",
      contentscripttype: "contentScriptType",
      contentstyletype: "contentStyleType",
      cursor: "cursor",
      cx: "cx",
      cy: "cy",
      d: "d",
      datatype: "datatype",
      decelerate: "decelerate",
      descent: "descent",
      diffuseconstant: "diffuseConstant",
      direction: "direction",
      display: "display",
      divisor: "divisor",
      dominantbaseline: "dominantBaseline",
      "dominant-baseline": "dominantBaseline",
      dur: "dur",
      dx: "dx",
      dy: "dy",
      edgemode: "edgeMode",
      elevation: "elevation",
      enablebackground: "enableBackground",
      "enable-background": "enableBackground",
      end: "end",
      exponent: "exponent",
      externalresourcesrequired: "externalResourcesRequired",
      fill: "fill",
      fillopacity: "fillOpacity",
      "fill-opacity": "fillOpacity",
      fillrule: "fillRule",
      "fill-rule": "fillRule",
      filter: "filter",
      filterres: "filterRes",
      filterunits: "filterUnits",
      floodopacity: "floodOpacity",
      "flood-opacity": "floodOpacity",
      floodcolor: "floodColor",
      "flood-color": "floodColor",
      focusable: "focusable",
      fontfamily: "fontFamily",
      "font-family": "fontFamily",
      fontsize: "fontSize",
      "font-size": "fontSize",
      fontsizeadjust: "fontSizeAdjust",
      "font-size-adjust": "fontSizeAdjust",
      fontstretch: "fontStretch",
      "font-stretch": "fontStretch",
      fontstyle: "fontStyle",
      "font-style": "fontStyle",
      fontvariant: "fontVariant",
      "font-variant": "fontVariant",
      fontweight: "fontWeight",
      "font-weight": "fontWeight",
      format: "format",
      from: "from",
      fx: "fx",
      fy: "fy",
      g1: "g1",
      g2: "g2",
      glyphname: "glyphName",
      "glyph-name": "glyphName",
      glyphorientationhorizontal: "glyphOrientationHorizontal",
      "glyph-orientation-horizontal": "glyphOrientationHorizontal",
      glyphorientationvertical: "glyphOrientationVertical",
      "glyph-orientation-vertical": "glyphOrientationVertical",
      glyphref: "glyphRef",
      gradienttransform: "gradientTransform",
      gradientunits: "gradientUnits",
      hanging: "hanging",
      horizadvx: "horizAdvX",
      "horiz-adv-x": "horizAdvX",
      horizoriginx: "horizOriginX",
      "horiz-origin-x": "horizOriginX",
      ideographic: "ideographic",
      imagerendering: "imageRendering",
      "image-rendering": "imageRendering",
      in2: "in2",
      in: "in",
      inlist: "inlist",
      intercept: "intercept",
      k1: "k1",
      k2: "k2",
      k3: "k3",
      k4: "k4",
      k: "k",
      kernelmatrix: "kernelMatrix",
      kernelunitlength: "kernelUnitLength",
      kerning: "kerning",
      keypoints: "keyPoints",
      keysplines: "keySplines",
      keytimes: "keyTimes",
      lengthadjust: "lengthAdjust",
      letterspacing: "letterSpacing",
      "letter-spacing": "letterSpacing",
      lightingcolor: "lightingColor",
      "lighting-color": "lightingColor",
      limitingconeangle: "limitingConeAngle",
      local: "local",
      markerend: "markerEnd",
      "marker-end": "markerEnd",
      markerheight: "markerHeight",
      markermid: "markerMid",
      "marker-mid": "markerMid",
      markerstart: "markerStart",
      "marker-start": "markerStart",
      markerunits: "markerUnits",
      markerwidth: "markerWidth",
      mask: "mask",
      maskcontentunits: "maskContentUnits",
      maskunits: "maskUnits",
      mathematical: "mathematical",
      mode: "mode",
      numoctaves: "numOctaves",
      offset: "offset",
      opacity: "opacity",
      operator: "operator",
      order: "order",
      orient: "orient",
      orientation: "orientation",
      origin: "origin",
      overflow: "overflow",
      overlineposition: "overlinePosition",
      "overline-position": "overlinePosition",
      overlinethickness: "overlineThickness",
      "overline-thickness": "overlineThickness",
      paintorder: "paintOrder",
      "paint-order": "paintOrder",
      panose1: "panose1",
      "panose-1": "panose1",
      pathlength: "pathLength",
      patterncontentunits: "patternContentUnits",
      patterntransform: "patternTransform",
      patternunits: "patternUnits",
      pointerevents: "pointerEvents",
      "pointer-events": "pointerEvents",
      points: "points",
      pointsatx: "pointsAtX",
      pointsaty: "pointsAtY",
      pointsatz: "pointsAtZ",
      prefix: "prefix",
      preservealpha: "preserveAlpha",
      preserveaspectratio: "preserveAspectRatio",
      primitiveunits: "primitiveUnits",
      property: "property",
      r: "r",
      radius: "radius",
      refx: "refX",
      refy: "refY",
      renderingintent: "renderingIntent",
      "rendering-intent": "renderingIntent",
      repeatcount: "repeatCount",
      repeatdur: "repeatDur",
      requiredextensions: "requiredExtensions",
      requiredfeatures: "requiredFeatures",
      resource: "resource",
      restart: "restart",
      result: "result",
      results: "results",
      rotate: "rotate",
      rx: "rx",
      ry: "ry",
      scale: "scale",
      security: "security",
      seed: "seed",
      shaperendering: "shapeRendering",
      "shape-rendering": "shapeRendering",
      slope: "slope",
      spacing: "spacing",
      specularconstant: "specularConstant",
      specularexponent: "specularExponent",
      speed: "speed",
      spreadmethod: "spreadMethod",
      startoffset: "startOffset",
      stddeviation: "stdDeviation",
      stemh: "stemh",
      stemv: "stemv",
      stitchtiles: "stitchTiles",
      stopcolor: "stopColor",
      "stop-color": "stopColor",
      stopopacity: "stopOpacity",
      "stop-opacity": "stopOpacity",
      strikethroughposition: "strikethroughPosition",
      "strikethrough-position": "strikethroughPosition",
      strikethroughthickness: "strikethroughThickness",
      "strikethrough-thickness": "strikethroughThickness",
      string: "string",
      stroke: "stroke",
      strokedasharray: "strokeDasharray",
      "stroke-dasharray": "strokeDasharray",
      strokedashoffset: "strokeDashoffset",
      "stroke-dashoffset": "strokeDashoffset",
      strokelinecap: "strokeLinecap",
      "stroke-linecap": "strokeLinecap",
      strokelinejoin: "strokeLinejoin",
      "stroke-linejoin": "strokeLinejoin",
      strokemiterlimit: "strokeMiterlimit",
      "stroke-miterlimit": "strokeMiterlimit",
      strokewidth: "strokeWidth",
      "stroke-width": "strokeWidth",
      strokeopacity: "strokeOpacity",
      "stroke-opacity": "strokeOpacity",
      suppresscontenteditablewarning: "suppressContentEditableWarning",
      suppresshydrationwarning: "suppressHydrationWarning",
      surfacescale: "surfaceScale",
      systemlanguage: "systemLanguage",
      tablevalues: "tableValues",
      targetx: "targetX",
      targety: "targetY",
      textanchor: "textAnchor",
      "text-anchor": "textAnchor",
      textdecoration: "textDecoration",
      "text-decoration": "textDecoration",
      textlength: "textLength",
      textrendering: "textRendering",
      "text-rendering": "textRendering",
      to: "to",
      transform: "transform",
      typeof: "typeof",
      u1: "u1",
      u2: "u2",
      underlineposition: "underlinePosition",
      "underline-position": "underlinePosition",
      underlinethickness: "underlineThickness",
      "underline-thickness": "underlineThickness",
      unicode: "unicode",
      unicodebidi: "unicodeBidi",
      "unicode-bidi": "unicodeBidi",
      unicoderange: "unicodeRange",
      "unicode-range": "unicodeRange",
      unitsperem: "unitsPerEm",
      "units-per-em": "unitsPerEm",
      unselectable: "unselectable",
      valphabetic: "vAlphabetic",
      "v-alphabetic": "vAlphabetic",
      values: "values",
      vectoreffect: "vectorEffect",
      "vector-effect": "vectorEffect",
      version: "version",
      vertadvy: "vertAdvY",
      "vert-adv-y": "vertAdvY",
      vertoriginx: "vertOriginX",
      "vert-origin-x": "vertOriginX",
      vertoriginy: "vertOriginY",
      "vert-origin-y": "vertOriginY",
      vhanging: "vHanging",
      "v-hanging": "vHanging",
      videographic: "vIdeographic",
      "v-ideographic": "vIdeographic",
      viewbox: "viewBox",
      viewtarget: "viewTarget",
      visibility: "visibility",
      vmathematical: "vMathematical",
      "v-mathematical": "vMathematical",
      vocab: "vocab",
      widths: "widths",
      wordspacing: "wordSpacing",
      "word-spacing": "wordSpacing",
      writingmode: "writingMode",
      "writing-mode": "writingMode",
      x1: "x1",
      x2: "x2",
      x: "x",
      xchannelselector: "xChannelSelector",
      xheight: "xHeight",
      "x-height": "xHeight",
      xlinkactuate: "xlinkActuate",
      "xlink:actuate": "xlinkActuate",
      xlinkarcrole: "xlinkArcrole",
      "xlink:arcrole": "xlinkArcrole",
      xlinkhref: "xlinkHref",
      "xlink:href": "xlinkHref",
      xlinkrole: "xlinkRole",
      "xlink:role": "xlinkRole",
      xlinkshow: "xlinkShow",
      "xlink:show": "xlinkShow",
      xlinktitle: "xlinkTitle",
      "xlink:title": "xlinkTitle",
      xlinktype: "xlinkType",
      "xlink:type": "xlinkType",
      xmlbase: "xmlBase",
      "xml:base": "xmlBase",
      xmllang: "xmlLang",
      "xml:lang": "xmlLang",
      xmlns: "xmlns",
      "xml:space": "xmlSpace",
      xmlnsxlink: "xmlnsXlink",
      "xmlns:xlink": "xmlnsXlink",
      xmlspace: "xmlSpace",
      y1: "y1",
      y2: "y2",
      y: "y",
      ychannelselector: "yChannelSelector",
      z: "z",
      zoomandpan: "zoomAndPan"
    }, wh = {
      "aria-current": 0,
      // state
      "aria-description": 0,
      "aria-details": 0,
      "aria-disabled": 0,
      // state
      "aria-hidden": 0,
      // state
      "aria-invalid": 0,
      // state
      "aria-keyshortcuts": 0,
      "aria-label": 0,
      "aria-roledescription": 0,
      // Widget Attributes
      "aria-autocomplete": 0,
      "aria-checked": 0,
      "aria-expanded": 0,
      "aria-haspopup": 0,
      "aria-level": 0,
      "aria-modal": 0,
      "aria-multiline": 0,
      "aria-multiselectable": 0,
      "aria-orientation": 0,
      "aria-placeholder": 0,
      "aria-pressed": 0,
      "aria-readonly": 0,
      "aria-required": 0,
      "aria-selected": 0,
      "aria-sort": 0,
      "aria-valuemax": 0,
      "aria-valuemin": 0,
      "aria-valuenow": 0,
      "aria-valuetext": 0,
      // Live Region Attributes
      "aria-atomic": 0,
      "aria-busy": 0,
      "aria-live": 0,
      "aria-relevant": 0,
      // Drag-and-Drop Attributes
      "aria-dropeffect": 0,
      "aria-grabbed": 0,
      // Relationship Attributes
      "aria-activedescendant": 0,
      "aria-colcount": 0,
      "aria-colindex": 0,
      "aria-colspan": 0,
      "aria-controls": 0,
      "aria-describedby": 0,
      "aria-errormessage": 0,
      "aria-flowto": 0,
      "aria-labelledby": 0,
      "aria-owns": 0,
      "aria-posinset": 0,
      "aria-rowcount": 0,
      "aria-rowindex": 0,
      "aria-rowspan": 0,
      "aria-setsize": 0
    }, _u = {}, ku = new RegExp("^(aria)-[" + xe + "]*$"), Kd = new RegExp("^(aria)[A-Z][" + xe + "]*$");
    function As(e, t) {
      {
        if (Te.call(_u, t) && _u[t])
          return !0;
        if (Kd.test(t)) {
          var a = "aria-" + t.slice(4).toLowerCase(), i = wh.hasOwnProperty(a) ? a : null;
          if (i == null)
            return g("Invalid ARIA attribute `%s`. ARIA attributes follow the pattern aria-* and must be lowercase.", t), _u[t] = !0, !0;
          if (t !== i)
            return g("Invalid ARIA attribute `%s`. Did you mean `%s`?", t, i), _u[t] = !0, !0;
        }
        if (ku.test(t)) {
          var l = t.toLowerCase(), c = wh.hasOwnProperty(l) ? l : null;
          if (c == null)
            return _u[t] = !0, !1;
          if (t !== c)
            return g("Unknown ARIA attribute `%s`. Did you mean `%s`?", t, c), _u[t] = !0, !0;
        }
      }
      return !0;
    }
    function Xd(e, t) {
      {
        var a = [];
        for (var i in t) {
          var l = As(e, i);
          l || a.push(i);
        }
        var c = a.map(function(p) {
          return "`" + p + "`";
        }).join(", ");
        a.length === 1 ? g("Invalid aria prop %s on <%s> tag. For details, see https://reactjs.org/link/invalid-aria-props", c, e) : a.length > 1 && g("Invalid aria props %s on <%s> tag. For details, see https://reactjs.org/link/invalid-aria-props", c, e);
      }
    }
    function xh(e, t) {
      $o(e, t) || Xd(e, t);
    }
    var Ms = !1;
    function Ou(e, t) {
      {
        if (e !== "input" && e !== "textarea" && e !== "select")
          return;
        t != null && t.value === null && !Ms && (Ms = !0, e === "select" && t.multiple ? g("`value` prop on `%s` should not be null. Consider using an empty array when `multiple` is set to `true` to clear the component or `undefined` for uncontrolled components.", e) : g("`value` prop on `%s` should not be null. Consider using an empty string to clear the component or `undefined` for uncontrolled components.", e));
      }
    }
    var Kc = function() {
    };
    {
      var jr = {}, Ls = /^on./, _h = /^on[^A-Z]/, kh = new RegExp("^(aria)-[" + xe + "]*$"), Oh = new RegExp("^(aria)[A-Z][" + xe + "]*$");
      Kc = function(e, t, a, i) {
        if (Te.call(jr, t) && jr[t])
          return !0;
        var l = t.toLowerCase();
        if (l === "onfocusin" || l === "onfocusout")
          return g("React uses onFocus and onBlur instead of onFocusIn and onFocusOut. All React events are normalized to bubble, so onFocusIn and onFocusOut are not needed/supported by React."), jr[t] = !0, !0;
        if (i != null) {
          var c = i.registrationNameDependencies, p = i.possibleRegistrationNames;
          if (c.hasOwnProperty(t))
            return !0;
          var m = p.hasOwnProperty(l) ? p[l] : null;
          if (m != null)
            return g("Invalid event handler property `%s`. Did you mean `%s`?", t, m), jr[t] = !0, !0;
          if (Ls.test(t))
            return g("Unknown event handler property `%s`. It will be ignored.", t), jr[t] = !0, !0;
        } else if (Ls.test(t))
          return _h.test(t) && g("Invalid event handler property `%s`. React events use the camelCase naming convention, for example `onClick`.", t), jr[t] = !0, !0;
        if (kh.test(t) || Oh.test(t))
          return !0;
        if (l === "innerhtml")
          return g("Directly setting property `innerHTML` is not permitted. For more information, lookup documentation on `dangerouslySetInnerHTML`."), jr[t] = !0, !0;
        if (l === "aria")
          return g("The `aria` attribute is reserved for future use in React. Pass individual `aria-` attributes instead."), jr[t] = !0, !0;
        if (l === "is" && a !== null && a !== void 0 && typeof a != "string")
          return g("Received a `%s` for a string attribute `is`. If this is expected, cast the value to a string.", typeof a), jr[t] = !0, !0;
        if (typeof a == "number" && isNaN(a))
          return g("Received NaN for the `%s` attribute. If this is expected, cast the value to a string.", t), jr[t] = !0, !0;
        var E = gn(t), R = E !== null && E.type === pr;
        if (xu.hasOwnProperty(l)) {
          var w = xu[l];
          if (w !== t)
            return g("Invalid DOM property `%s`. Did you mean `%s`?", t, w), jr[t] = !0, !0;
        } else if (!R && t !== l)
          return g("React does not recognize the `%s` prop on a DOM element. If you intentionally want it to appear in the DOM as a custom attribute, spell it as lowercase `%s` instead. If you accidentally passed it from a parent component, remove it from the DOM element.", t, l), jr[t] = !0, !0;
        return typeof a == "boolean" && Rn(t, a, E, !1) ? (a ? g('Received `%s` for a non-boolean attribute `%s`.\n\nIf you want to write it to the DOM, pass a string instead: %s="%s" or %s={value.toString()}.', a, t, t, a, t) : g('Received `%s` for a non-boolean attribute `%s`.\n\nIf you want to write it to the DOM, pass a string instead: %s="%s" or %s={value.toString()}.\n\nIf you used to conditionally omit it with %s={condition && value}, pass %s={condition ? value : undefined} instead.', a, t, t, a, t, t, t), jr[t] = !0, !0) : R ? !0 : Rn(t, a, E, !1) ? (jr[t] = !0, !1) : ((a === "false" || a === "true") && E !== null && E.type === Qn && (g("Received the string `%s` for the boolean attribute `%s`. %s Did you mean %s={%s}?", a, t, a === "false" ? "The browser will interpret it as a truthy value." : 'Although this works, it will not work as expected if you pass the string "false".', t, a), jr[t] = !0), !0);
      };
    }
    var Dh = function(e, t, a) {
      {
        var i = [];
        for (var l in t) {
          var c = Kc(e, l, t[l], a);
          c || i.push(l);
        }
        var p = i.map(function(m) {
          return "`" + m + "`";
        }).join(", ");
        i.length === 1 ? g("Invalid value for prop %s on <%s> tag. Either remove it from the element, or pass a string or number value to keep it in the DOM. For details, see https://reactjs.org/link/attribute-behavior ", p, e) : i.length > 1 && g("Invalid values for props %s on <%s> tag. Either remove them from the element, or pass a string or number value to keep them in the DOM. For details, see https://reactjs.org/link/attribute-behavior ", p, e);
      }
    };
    function Nh(e, t, a) {
      $o(e, t) || Dh(e, t, a);
    }
    var Jd = 1, $i = 2, Ol = 4, Zd = Jd | $i | Ol, zs = null;
    function Lg(e) {
      zs !== null && g("Expected currently replaying event to be null. This error is likely caused by a bug in React. Please file an issue."), zs = e;
    }
    function Us() {
      zs === null && g("Expected currently replaying event to not be null. This error is likely caused by a bug in React. Please file an issue."), zs = null;
    }
    function zg(e) {
      return e === zs;
    }
    function Xc(e) {
      var t = e.target || e.srcElement || window;
      return t.correspondingUseElement && (t = t.correspondingUseElement), t.nodeType === fo ? t.parentNode : t;
    }
    var Jc = null, Xt = null, Fo = null;
    function Ps(e) {
      var t = ns(e);
      if (t) {
        if (typeof Jc != "function")
          throw new Error("setRestoreImplementation() needs to be called to handle a target for controlled events. This error is likely caused by a bug in React. Please file an issue.");
        var a = t.stateNode;
        if (a) {
          var i = Um(a);
          Jc(t.stateNode, t.type, i);
        }
      }
    }
    function $s(e) {
      Jc = e;
    }
    function ep(e) {
      Xt ? Fo ? Fo.push(e) : Fo = [e] : Xt = e;
    }
    function tp() {
      return Xt !== null || Fo !== null;
    }
    function Du() {
      if (Xt) {
        var e = Xt, t = Fo;
        if (Xt = null, Fo = null, Ps(e), t)
          for (var a = 0; a < t.length; a++)
            Ps(t[a]);
      }
    }
    var Fs = function(e, t) {
      return e(t);
    }, Dl = function() {
    }, Zc = !1;
    function Ug() {
      var e = tp();
      e && (Dl(), Du());
    }
    function Ah(e, t, a) {
      if (Zc)
        return e(t, a);
      Zc = !0;
      try {
        return Fs(e, t, a);
      } finally {
        Zc = !1, Ug();
      }
    }
    function Mh(e, t, a) {
      Fs = e, Dl = a;
    }
    function ef(e) {
      return e === "button" || e === "input" || e === "select" || e === "textarea";
    }
    function tf(e, t, a) {
      switch (e) {
        case "onClick":
        case "onClickCapture":
        case "onDoubleClick":
        case "onDoubleClickCapture":
        case "onMouseDown":
        case "onMouseDownCapture":
        case "onMouseMove":
        case "onMouseMoveCapture":
        case "onMouseUp":
        case "onMouseUpCapture":
        case "onMouseEnter":
          return !!(a.disabled && ef(t));
        default:
          return !1;
      }
    }
    function Nl(e, t) {
      var a = e.stateNode;
      if (a === null)
        return null;
      var i = Um(a);
      if (i === null)
        return null;
      var l = i[t];
      if (tf(t, e.type, i))
        return null;
      if (l && typeof l != "function")
        throw new Error("Expected `" + t + "` listener to be a function, instead got a value of `" + typeof l + "` type.");
      return l;
    }
    var js = !1;
    if (Ht)
      try {
        var Al = {};
        Object.defineProperty(Al, "passive", {
          get: function() {
            js = !0;
          }
        }), window.addEventListener("test", Al, Al), window.removeEventListener("test", Al, Al);
      } catch {
        js = !1;
      }
    function nf(e, t, a, i, l, c, p, m, E) {
      var R = Array.prototype.slice.call(arguments, 3);
      try {
        t.apply(a, R);
      } catch (w) {
        this.onError(w);
      }
    }
    var Lh = nf;
    if (typeof window < "u" && typeof window.dispatchEvent == "function" && typeof document < "u" && typeof document.createEvent == "function") {
      var rf = document.createElement("react");
      Lh = function(t, a, i, l, c, p, m, E, R) {
        if (typeof document > "u" || document === null)
          throw new Error("The `document` global was defined when React was initialized, but is not defined anymore. This can happen in a test environment if a component schedules an update from an asynchronous callback, but the test has already finished running. To solve this, you can either unmount the component at the end of your test (and ensure that any asynchronous operations get canceled in `componentWillUnmount`), or you can change the test itself to be asynchronous.");
        var w = document.createEvent("Event"), V = !1, $ = !0, X = window.event, Z = Object.getOwnPropertyDescriptor(window, "event");
        function ne() {
          rf.removeEventListener(re, lt, !1), typeof window.event < "u" && window.hasOwnProperty("event") && (window.event = X);
        }
        var Me = Array.prototype.slice.call(arguments, 3);
        function lt() {
          V = !0, ne(), a.apply(i, Me), $ = !1;
        }
        var tt, jt = !1, Lt = !1;
        function W(G) {
          if (tt = G.error, jt = !0, tt === null && G.colno === 0 && G.lineno === 0 && (Lt = !0), G.defaultPrevented && tt != null && typeof tt == "object")
            try {
              tt._suppressLogging = !0;
            } catch {
            }
        }
        var re = "react-" + (t || "invokeguardedcallback");
        if (window.addEventListener("error", W), rf.addEventListener(re, lt, !1), w.initEvent(re, !1, !1), rf.dispatchEvent(w), Z && Object.defineProperty(window, "event", Z), V && $ && (jt ? Lt && (tt = new Error("A cross-origin error was thrown. React doesn't have access to the actual error object in development. See https://reactjs.org/link/crossorigin-error for more information.")) : tt = new Error(`An error was thrown inside one of your components, but React doesn't know what it was. This is likely due to browser flakiness. React does its best to preserve the "Pause on exceptions" behavior of the DevTools, which requires some DEV-mode only tricks. It's possible that these don't work in your browser. Try triggering the error in production mode, or switching to a modern browser. If you suspect that this is actually an issue with React, please file an issue.`), this.onError(tt)), window.removeEventListener("error", W), !V)
          return ne(), nf.apply(this, arguments);
      };
    }
    var Pg = Lh, Nu = !1, Au = null, gi = !1, af = null, Mu = {
      onError: function(e) {
        Nu = !0, Au = e;
      }
    };
    function Ka(e, t, a, i, l, c, p, m, E) {
      Nu = !1, Au = null, Pg.apply(Mu, arguments);
    }
    function Hs(e, t, a, i, l, c, p, m, E) {
      if (Ka.apply(this, arguments), Nu) {
        var R = rp();
        gi || (gi = !0, af = R);
      }
    }
    function vo() {
      if (gi) {
        var e = af;
        throw gi = !1, af = null, e;
      }
    }
    function np() {
      return Nu;
    }
    function rp() {
      if (Nu) {
        var e = Au;
        return Nu = !1, Au = null, e;
      } else
        throw new Error("clearCaughtError was called but no error was captured. This error is likely caused by a bug in React. Please file an issue.");
    }
    function Lu(e) {
      return e._reactInternals;
    }
    function Ml(e) {
      return e._reactInternals !== void 0;
    }
    function Vs(e, t) {
      e._reactInternals = t;
    }
    var nt = (
      /*                      */
      0
    ), ho = (
      /*                */
      1
    ), Kn = (
      /*                    */
      2
    ), At = (
      /*                       */
      4
    ), pa = (
      /*                */
      16
    ), sn = (
      /*                 */
      32
    ), mn = (
      /*                     */
      64
    ), Ot = (
      /*                   */
      128
    ), Un = (
      /*            */
      256
    ), Xn = (
      /*                          */
      512
    ), Xa = (
      /*                     */
      1024
    ), Aa = (
      /*                      */
      2048
    ), Jn = (
      /*                    */
      4096
    ), Fi = (
      /*                   */
      8192
    ), of = (
      /*             */
      16384
    ), zh = (
      /*               */
      32767
    ), Ll = (
      /*                   */
      32768
    ), Ja = (
      /*                */
      65536
    ), Si = (
      /* */
      131072
    ), Bs = (
      /*                       */
      1048576
    ), Is = (
      /*                    */
      2097152
    ), jo = (
      /*                 */
      4194304
    ), ap = (
      /*                */
      8388608
    ), Qr = (
      /*               */
      16777216
    ), Ho = (
      /*              */
      33554432
    ), Vo = (
      // TODO: Remove Update flag from before mutation phase by re-landing Visibility
      // flag logic (see #20043)
      At | Xa | 0
    ), zu = Kn | At | pa | sn | Xn | Jn | Fi, Bo = At | mn | Xn | Fi, Rr = Aa | pa, Zn = jo | ap | Is, zl = y.ReactCurrentOwner;
    function qr(e) {
      var t = e, a = e;
      if (e.alternate)
        for (; t.return; )
          t = t.return;
      else {
        var i = t;
        do
          t = i, (t.flags & (Kn | Jn)) !== nt && (a = t.return), i = t.return;
        while (i);
      }
      return t.tag === U ? a : null;
    }
    function ji(e) {
      if (e.tag === se) {
        var t = e.memoizedState;
        if (t === null) {
          var a = e.alternate;
          a !== null && (t = a.memoizedState);
        }
        if (t !== null)
          return t.dehydrated;
      }
      return null;
    }
    function Io(e) {
      return e.tag === U ? e.stateNode.containerInfo : null;
    }
    function Uh(e) {
      return qr(e) === e;
    }
    function ip(e) {
      {
        var t = zl.current;
        if (t !== null && t.tag === A) {
          var a = t, i = a.stateNode;
          i._warnedAboutRefsInRender || g("%s is accessing isMounted inside its render() function. render() should be a pure function of props and state. It should never access something that requires stale data from the previous render, such as refs. Move this logic to componentDidMount and componentDidUpdate instead.", ht(a) || "A component"), i._warnedAboutRefsInRender = !0;
        }
      }
      var l = Lu(e);
      return l ? qr(l) === l : !1;
    }
    function lf(e) {
      if (qr(e) !== e)
        throw new Error("Unable to find node on an unmounted component.");
    }
    function va(e) {
      var t = e.alternate;
      if (!t) {
        var a = qr(e);
        if (a === null)
          throw new Error("Unable to find node on an unmounted component.");
        return a !== e ? null : e;
      }
      for (var i = e, l = t; ; ) {
        var c = i.return;
        if (c === null)
          break;
        var p = c.alternate;
        if (p === null) {
          var m = c.return;
          if (m !== null) {
            i = l = m;
            continue;
          }
          break;
        }
        if (c.child === p.child) {
          for (var E = c.child; E; ) {
            if (E === i)
              return lf(c), e;
            if (E === l)
              return lf(c), t;
            E = E.sibling;
          }
          throw new Error("Unable to find node on an unmounted component.");
        }
        if (i.return !== l.return)
          i = c, l = p;
        else {
          for (var R = !1, w = c.child; w; ) {
            if (w === i) {
              R = !0, i = c, l = p;
              break;
            }
            if (w === l) {
              R = !0, l = c, i = p;
              break;
            }
            w = w.sibling;
          }
          if (!R) {
            for (w = p.child; w; ) {
              if (w === i) {
                R = !0, i = p, l = c;
                break;
              }
              if (w === l) {
                R = !0, l = p, i = c;
                break;
              }
              w = w.sibling;
            }
            if (!R)
              throw new Error("Child was not found in either parent set. This indicates a bug in React related to the return pointer. Please file an issue.");
          }
        }
        if (i.alternate !== l)
          throw new Error("Return fibers should always be each others' alternates. This error is likely caused by a bug in React. Please file an issue.");
      }
      if (i.tag !== U)
        throw new Error("Unable to find node on an unmounted component.");
      return i.stateNode.current === i ? e : t;
    }
    function ha(e) {
      var t = va(e);
      return t !== null ? xn(t) : null;
    }
    function xn(e) {
      if (e.tag === B || e.tag === M)
        return e;
      for (var t = e.child; t !== null; ) {
        var a = xn(t);
        if (a !== null)
          return a;
        t = t.sibling;
      }
      return null;
    }
    function Ei(e) {
      var t = va(e);
      return t !== null ? op(t) : null;
    }
    function op(e) {
      if (e.tag === B || e.tag === M)
        return e;
      for (var t = e.child; t !== null; ) {
        if (t.tag !== te) {
          var a = op(t);
          if (a !== null)
            return a;
        }
        t = t.sibling;
      }
      return null;
    }
    var lp = v.unstable_scheduleCallback, up = v.unstable_cancelCallback, sp = v.unstable_shouldYield, Ph = v.unstable_requestPaint, Vn = v.unstable_now, $h = v.unstable_getCurrentPriorityLevel, mo = v.unstable_ImmediatePriority, Ys = v.unstable_UserBlockingPriority, Ul = v.unstable_NormalPriority, Ws = v.unstable_LowPriority, Uu = v.unstable_IdlePriority, Fh = v.unstable_yieldValue, jh = v.unstable_setDisableYieldValue, Ci = null, wr = null, Ne = null, Ma = !1, Hr = typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u";
    function cp(e) {
      if (typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u")
        return !1;
      var t = __REACT_DEVTOOLS_GLOBAL_HOOK__;
      if (t.isDisabled)
        return !0;
      if (!t.supportsFiber)
        return g("The installed version of React DevTools is too old and will not work with the current version of React. Please update React DevTools. https://reactjs.org/link/react-devtools"), !0;
      try {
        Re && (e = Et({}, e, {
          getLaneLabelMap: vp,
          injectProfilingHooks: Pl
        })), Ci = t.inject(e), wr = t;
      } catch (a) {
        g("React instrumentation encountered an error: %s.", a);
      }
      return !!t.checkDCE;
    }
    function fp(e, t) {
      if (wr && typeof wr.onScheduleFiberRoot == "function")
        try {
          wr.onScheduleFiberRoot(Ci, e, t);
        } catch (a) {
          Ma || (Ma = !0, g("React instrumentation encountered an error: %s", a));
        }
    }
    function dp(e, t) {
      if (wr && typeof wr.onCommitFiberRoot == "function")
        try {
          var a = (e.current.flags & Ot) === Ot;
          if (be) {
            var i;
            switch (t) {
              case Sa:
                i = mo;
                break;
              case ei:
                i = Ys;
                break;
              case xr:
                i = Ul;
                break;
              case Pf:
                i = Uu;
                break;
              default:
                i = Ul;
                break;
            }
            wr.onCommitFiberRoot(Ci, e, i, a);
          }
        } catch (l) {
          Ma || (Ma = !0, g("React instrumentation encountered an error: %s", l));
        }
    }
    function pp(e) {
      if (wr && typeof wr.onPostCommitFiberRoot == "function")
        try {
          wr.onPostCommitFiberRoot(Ci, e);
        } catch (t) {
          Ma || (Ma = !0, g("React instrumentation encountered an error: %s", t));
        }
    }
    function Pu(e) {
      if (wr && typeof wr.onCommitFiberUnmount == "function")
        try {
          wr.onCommitFiberUnmount(Ci, e);
        } catch (t) {
          Ma || (Ma = !0, g("React instrumentation encountered an error: %s", t));
        }
    }
    function en(e) {
      if (typeof Fh == "function" && (jh(e), T(e)), wr && typeof wr.setStrictMode == "function")
        try {
          wr.setStrictMode(Ci, e);
        } catch (t) {
          Ma || (Ma = !0, g("React instrumentation encountered an error: %s", t));
        }
    }
    function Pl(e) {
      Ne = e;
    }
    function vp() {
      {
        for (var e = /* @__PURE__ */ new Map(), t = 1, a = 0; a < Ep; a++) {
          var i = Wh(t);
          e.set(t, i), t *= 2;
        }
        return e;
      }
    }
    function Hh(e) {
      Ne !== null && typeof Ne.markCommitStarted == "function" && Ne.markCommitStarted(e);
    }
    function Hi() {
      Ne !== null && typeof Ne.markCommitStopped == "function" && Ne.markCommitStopped();
    }
    function Za(e) {
      Ne !== null && typeof Ne.markComponentRenderStarted == "function" && Ne.markComponentRenderStarted(e);
    }
    function Yo() {
      Ne !== null && typeof Ne.markComponentRenderStopped == "function" && Ne.markComponentRenderStopped();
    }
    function Vh(e) {
      Ne !== null && typeof Ne.markComponentPassiveEffectMountStarted == "function" && Ne.markComponentPassiveEffectMountStarted(e);
    }
    function yo() {
      Ne !== null && typeof Ne.markComponentPassiveEffectMountStopped == "function" && Ne.markComponentPassiveEffectMountStopped();
    }
    function Wo(e) {
      Ne !== null && typeof Ne.markComponentPassiveEffectUnmountStarted == "function" && Ne.markComponentPassiveEffectUnmountStarted(e);
    }
    function uf() {
      Ne !== null && typeof Ne.markComponentPassiveEffectUnmountStopped == "function" && Ne.markComponentPassiveEffectUnmountStopped();
    }
    function Bh(e) {
      Ne !== null && typeof Ne.markComponentLayoutEffectMountStarted == "function" && Ne.markComponentLayoutEffectMountStarted(e);
    }
    function sf() {
      Ne !== null && typeof Ne.markComponentLayoutEffectMountStopped == "function" && Ne.markComponentLayoutEffectMountStopped();
    }
    function hp(e) {
      Ne !== null && typeof Ne.markComponentLayoutEffectUnmountStarted == "function" && Ne.markComponentLayoutEffectUnmountStarted(e);
    }
    function $u() {
      Ne !== null && typeof Ne.markComponentLayoutEffectUnmountStopped == "function" && Ne.markComponentLayoutEffectUnmountStopped();
    }
    function Vi(e, t, a) {
      Ne !== null && typeof Ne.markComponentErrored == "function" && Ne.markComponentErrored(e, t, a);
    }
    function Gs(e, t, a) {
      Ne !== null && typeof Ne.markComponentSuspended == "function" && Ne.markComponentSuspended(e, t, a);
    }
    function Qs(e) {
      Ne !== null && typeof Ne.markLayoutEffectsStarted == "function" && Ne.markLayoutEffectsStarted(e);
    }
    function $l() {
      Ne !== null && typeof Ne.markLayoutEffectsStopped == "function" && Ne.markLayoutEffectsStopped();
    }
    function mp(e) {
      Ne !== null && typeof Ne.markPassiveEffectsStarted == "function" && Ne.markPassiveEffectsStarted(e);
    }
    function Fu() {
      Ne !== null && typeof Ne.markPassiveEffectsStopped == "function" && Ne.markPassiveEffectsStopped();
    }
    function yp(e) {
      Ne !== null && typeof Ne.markRenderStarted == "function" && Ne.markRenderStarted(e);
    }
    function gp() {
      Ne !== null && typeof Ne.markRenderYielded == "function" && Ne.markRenderYielded();
    }
    function Nn() {
      Ne !== null && typeof Ne.markRenderStopped == "function" && Ne.markRenderStopped();
    }
    function cf(e) {
      Ne !== null && typeof Ne.markRenderScheduled == "function" && Ne.markRenderScheduled(e);
    }
    function Sp(e, t) {
      Ne !== null && typeof Ne.markForceUpdateScheduled == "function" && Ne.markForceUpdateScheduled(e, t);
    }
    function qs(e, t) {
      Ne !== null && typeof Ne.markStateUpdateScheduled == "function" && Ne.markStateUpdateScheduled(e, t);
    }
    var rt = (
      /*                         */
      0
    ), Dt = (
      /*                 */
      1
    ), zt = (
      /*                    */
      2
    ), Ct = (
      /*               */
      8
    ), cn = (
      /*              */
      16
    ), or = Math.clz32 ? Math.clz32 : Xs, ff = Math.log, Ks = Math.LN2;
    function Xs(e) {
      var t = e >>> 0;
      return t === 0 ? 32 : 31 - (ff(t) / Ks | 0) | 0;
    }
    var Ep = 31, oe = (
      /*                        */
      0
    ), er = (
      /*                          */
      0
    ), ct = (
      /*                        */
      1
    ), Go = (
      /*    */
      2
    ), mr = (
      /*             */
      4
    ), yr = (
      /*            */
      8
    ), ma = (
      /*                     */
      16
    ), Fl = (
      /*                */
      32
    ), Qo = (
      /*                       */
      4194240
    ), ju = (
      /*                        */
      64
    ), df = (
      /*                        */
      128
    ), pf = (
      /*                        */
      256
    ), vf = (
      /*                        */
      512
    ), hf = (
      /*                        */
      1024
    ), mf = (
      /*                        */
      2048
    ), yf = (
      /*                        */
      4096
    ), gf = (
      /*                        */
      8192
    ), jl = (
      /*                        */
      16384
    ), Sf = (
      /*                       */
      32768
    ), Hu = (
      /*                       */
      65536
    ), Vu = (
      /*                       */
      131072
    ), Ef = (
      /*                       */
      262144
    ), Js = (
      /*                       */
      524288
    ), Cf = (
      /*                       */
      1048576
    ), bf = (
      /*                       */
      2097152
    ), Zs = (
      /*                            */
      130023424
    ), Hl = (
      /*                             */
      4194304
    ), ec = (
      /*                             */
      8388608
    ), Tf = (
      /*                             */
      16777216
    ), Rf = (
      /*                             */
      33554432
    ), wf = (
      /*                             */
      67108864
    ), Ih = Hl, Bu = (
      /*          */
      134217728
    ), Yh = (
      /*                          */
      268435455
    ), tc = (
      /*               */
      268435456
    ), qo = (
      /*                        */
      536870912
    ), La = (
      /*                   */
      1073741824
    );
    function Wh(e) {
      {
        if (e & ct)
          return "Sync";
        if (e & Go)
          return "InputContinuousHydration";
        if (e & mr)
          return "InputContinuous";
        if (e & yr)
          return "DefaultHydration";
        if (e & ma)
          return "Default";
        if (e & Fl)
          return "TransitionHydration";
        if (e & Qo)
          return "Transition";
        if (e & Zs)
          return "Retry";
        if (e & Bu)
          return "SelectiveHydration";
        if (e & tc)
          return "IdleHydration";
        if (e & qo)
          return "Idle";
        if (e & La)
          return "Offscreen";
      }
    }
    var tn = -1, xf = ju, _f = Hl;
    function nc(e) {
      switch (Vl(e)) {
        case ct:
          return ct;
        case Go:
          return Go;
        case mr:
          return mr;
        case yr:
          return yr;
        case ma:
          return ma;
        case Fl:
          return Fl;
        case ju:
        case df:
        case pf:
        case vf:
        case hf:
        case mf:
        case yf:
        case gf:
        case jl:
        case Sf:
        case Hu:
        case Vu:
        case Ef:
        case Js:
        case Cf:
        case bf:
          return e & Qo;
        case Hl:
        case ec:
        case Tf:
        case Rf:
        case wf:
          return e & Zs;
        case Bu:
          return Bu;
        case tc:
          return tc;
        case qo:
          return qo;
        case La:
          return La;
        default:
          return g("Should have found matching lanes. This is a bug in React."), e;
      }
    }
    function ya(e, t) {
      var a = e.pendingLanes;
      if (a === oe)
        return oe;
      var i = oe, l = e.suspendedLanes, c = e.pingedLanes, p = a & Yh;
      if (p !== oe) {
        var m = p & ~l;
        if (m !== oe)
          i = nc(m);
        else {
          var E = p & c;
          E !== oe && (i = nc(E));
        }
      } else {
        var R = a & ~l;
        R !== oe ? i = nc(R) : c !== oe && (i = nc(c));
      }
      if (i === oe)
        return oe;
      if (t !== oe && t !== i && // If we already suspended with a delay, then interrupting is fine. Don't
      // bother waiting until the root is complete.
      (t & l) === oe) {
        var w = Vl(i), V = Vl(t);
        if (
          // Tests whether the next lane is equal or lower priority than the wip
          // one. This works because the bits decrease in priority as you go left.
          w >= V || // Default priority updates should not interrupt transition updates. The
          // only difference between default updates and transition updates is that
          // default updates do not support refresh transitions.
          w === ma && (V & Qo) !== oe
        )
          return t;
      }
      (i & mr) !== oe && (i |= a & ma);
      var $ = e.entangledLanes;
      if ($ !== oe)
        for (var X = e.entanglements, Z = i & $; Z > 0; ) {
          var ne = Bn(Z), Me = 1 << ne;
          i |= X[ne], Z &= ~Me;
        }
      return i;
    }
    function Cp(e, t) {
      for (var a = e.eventTimes, i = tn; t > 0; ) {
        var l = Bn(t), c = 1 << l, p = a[l];
        p > i && (i = p), t &= ~c;
      }
      return i;
    }
    function kf(e, t) {
      switch (e) {
        case ct:
        case Go:
        case mr:
          return t + 250;
        case yr:
        case ma:
        case Fl:
        case ju:
        case df:
        case pf:
        case vf:
        case hf:
        case mf:
        case yf:
        case gf:
        case jl:
        case Sf:
        case Hu:
        case Vu:
        case Ef:
        case Js:
        case Cf:
        case bf:
          return t + 5e3;
        case Hl:
        case ec:
        case Tf:
        case Rf:
        case wf:
          return tn;
        case Bu:
        case tc:
        case qo:
        case La:
          return tn;
        default:
          return g("Should have found matching lanes. This is a bug in React."), tn;
      }
    }
    function Gh(e, t) {
      for (var a = e.pendingLanes, i = e.suspendedLanes, l = e.pingedLanes, c = e.expirationTimes, p = a; p > 0; ) {
        var m = Bn(p), E = 1 << m, R = c[m];
        R === tn ? ((E & i) === oe || (E & l) !== oe) && (c[m] = kf(E, t)) : R <= t && (e.expiredLanes |= E), p &= ~E;
      }
    }
    function Qh(e) {
      return nc(e.pendingLanes);
    }
    function Of(e) {
      var t = e.pendingLanes & -1073741825;
      return t !== oe ? t : t & La ? La : oe;
    }
    function bp(e) {
      return (e & ct) !== oe;
    }
    function Ko(e) {
      return (e & Yh) !== oe;
    }
    function Df(e) {
      return (e & Zs) === e;
    }
    function Tp(e) {
      var t = ct | mr | ma;
      return (e & t) === oe;
    }
    function $g(e) {
      return (e & Qo) === e;
    }
    function rc(e, t) {
      var a = Go | mr | yr | ma;
      return (t & a) !== oe;
    }
    function qh(e, t) {
      return (t & e.expiredLanes) !== oe;
    }
    function Rp(e) {
      return (e & Qo) !== oe;
    }
    function wp() {
      var e = xf;
      return xf <<= 1, (xf & Qo) === oe && (xf = ju), e;
    }
    function Kh() {
      var e = _f;
      return _f <<= 1, (_f & Zs) === oe && (_f = Hl), e;
    }
    function Vl(e) {
      return e & -e;
    }
    function gr(e) {
      return Vl(e);
    }
    function Bn(e) {
      return 31 - or(e);
    }
    function Nf(e) {
      return Bn(e);
    }
    function ga(e, t) {
      return (e & t) !== oe;
    }
    function Bl(e, t) {
      return (e & t) === t;
    }
    function Tt(e, t) {
      return e | t;
    }
    function ac(e, t) {
      return e & ~t;
    }
    function Af(e, t) {
      return e & t;
    }
    function Fg(e) {
      return e;
    }
    function xp(e, t) {
      return e !== er && e < t ? e : t;
    }
    function Mf(e) {
      for (var t = [], a = 0; a < Ep; a++)
        t.push(e);
      return t;
    }
    function Iu(e, t, a) {
      e.pendingLanes |= t, t !== qo && (e.suspendedLanes = oe, e.pingedLanes = oe);
      var i = e.eventTimes, l = Nf(t);
      i[l] = a;
    }
    function _p(e, t) {
      e.suspendedLanes |= t, e.pingedLanes &= ~t;
      for (var a = e.expirationTimes, i = t; i > 0; ) {
        var l = Bn(i), c = 1 << l;
        a[l] = tn, i &= ~c;
      }
    }
    function Lf(e, t, a) {
      e.pingedLanes |= e.suspendedLanes & t;
    }
    function Xh(e, t) {
      var a = e.pendingLanes & ~t;
      e.pendingLanes = t, e.suspendedLanes = oe, e.pingedLanes = oe, e.expiredLanes &= t, e.mutableReadLanes &= t, e.entangledLanes &= t;
      for (var i = e.entanglements, l = e.eventTimes, c = e.expirationTimes, p = a; p > 0; ) {
        var m = Bn(p), E = 1 << m;
        i[m] = oe, l[m] = tn, c[m] = tn, p &= ~E;
      }
    }
    function ic(e, t) {
      for (var a = e.entangledLanes |= t, i = e.entanglements, l = a; l; ) {
        var c = Bn(l), p = 1 << c;
        // Is this one of the newly entangled lanes?
        p & t | // Is this lane transitively entangled with the newly entangled lanes?
        i[c] & t && (i[c] |= t), l &= ~p;
      }
    }
    function zf(e, t) {
      var a = Vl(t), i;
      switch (a) {
        case mr:
          i = Go;
          break;
        case ma:
          i = yr;
          break;
        case ju:
        case df:
        case pf:
        case vf:
        case hf:
        case mf:
        case yf:
        case gf:
        case jl:
        case Sf:
        case Hu:
        case Vu:
        case Ef:
        case Js:
        case Cf:
        case bf:
        case Hl:
        case ec:
        case Tf:
        case Rf:
        case wf:
          i = Fl;
          break;
        case qo:
          i = tc;
          break;
        default:
          i = er;
          break;
      }
      return (i & (e.suspendedLanes | t)) !== er ? er : i;
    }
    function Jh(e, t, a) {
      if (Hr)
        for (var i = e.pendingUpdatersLaneMap; a > 0; ) {
          var l = Nf(a), c = 1 << l, p = i[l];
          p.add(t), a &= ~c;
        }
    }
    function kp(e, t) {
      if (Hr)
        for (var a = e.pendingUpdatersLaneMap, i = e.memoizedUpdaters; t > 0; ) {
          var l = Nf(t), c = 1 << l, p = a[l];
          p.size > 0 && (p.forEach(function(m) {
            var E = m.alternate;
            (E === null || !i.has(E)) && i.add(m);
          }), p.clear()), t &= ~c;
        }
    }
    function Uf(e, t) {
      return null;
    }
    var Sa = ct, ei = mr, xr = ma, Pf = qo, Yu = er;
    function za() {
      return Yu;
    }
    function lr(e) {
      Yu = e;
    }
    function Zh(e, t) {
      var a = Yu;
      try {
        return Yu = e, t();
      } finally {
        Yu = a;
      }
    }
    function oc(e, t) {
      return e !== 0 && e < t ? e : t;
    }
    function Vr(e, t) {
      return e > t ? e : t;
    }
    function Op(e, t) {
      return e !== 0 && e < t;
    }
    function em(e) {
      var t = Vl(e);
      return Op(Sa, t) ? Op(ei, t) ? Ko(t) ? xr : Pf : ei : Sa;
    }
    function Il(e) {
      var t = e.current.memoizedState;
      return t.isDehydrated;
    }
    var _r;
    function jg(e) {
      _r = e;
    }
    function qe(e) {
      _r(e);
    }
    var Xo;
    function Dp(e) {
      Xo = e;
    }
    var Np;
    function Hg(e) {
      Np = e;
    }
    var Wu;
    function $f(e) {
      Wu = e;
    }
    var Ff;
    function tm(e) {
      Ff = e;
    }
    var jf = !1, lc = [], Bi = null, Ii = null, An = null, Kr = /* @__PURE__ */ new Map(), ti = /* @__PURE__ */ new Map(), go = [], nm = [
      "mousedown",
      "mouseup",
      "touchcancel",
      "touchend",
      "touchstart",
      "auxclick",
      "dblclick",
      "pointercancel",
      "pointerdown",
      "pointerup",
      "dragend",
      "dragstart",
      "drop",
      "compositionend",
      "compositionstart",
      "keydown",
      "keypress",
      "keyup",
      "input",
      "textInput",
      // Intentionally camelCase
      "copy",
      "cut",
      "paste",
      "click",
      "change",
      "contextmenu",
      "reset",
      "submit"
    ];
    function bi(e) {
      return nm.indexOf(e) > -1;
    }
    function rm(e, t, a, i, l) {
      return {
        blockedOn: e,
        domEventName: t,
        eventSystemFlags: a,
        nativeEvent: l,
        targetContainers: [i]
      };
    }
    function Ti(e, t) {
      switch (e) {
        case "focusin":
        case "focusout":
          Bi = null;
          break;
        case "dragenter":
        case "dragleave":
          Ii = null;
          break;
        case "mouseover":
        case "mouseout":
          An = null;
          break;
        case "pointerover":
        case "pointerout": {
          var a = t.pointerId;
          Kr.delete(a);
          break;
        }
        case "gotpointercapture":
        case "lostpointercapture": {
          var i = t.pointerId;
          ti.delete(i);
          break;
        }
      }
    }
    function uc(e, t, a, i, l, c) {
      if (e === null || e.nativeEvent !== c) {
        var p = rm(t, a, i, l, c);
        if (t !== null) {
          var m = ns(t);
          m !== null && Xo(m);
        }
        return p;
      }
      e.eventSystemFlags |= i;
      var E = e.targetContainers;
      return l !== null && E.indexOf(l) === -1 && E.push(l), e;
    }
    function am(e, t, a, i, l) {
      switch (t) {
        case "focusin": {
          var c = l;
          return Bi = uc(Bi, e, t, a, i, c), !0;
        }
        case "dragenter": {
          var p = l;
          return Ii = uc(Ii, e, t, a, i, p), !0;
        }
        case "mouseover": {
          var m = l;
          return An = uc(An, e, t, a, i, m), !0;
        }
        case "pointerover": {
          var E = l, R = E.pointerId;
          return Kr.set(R, uc(Kr.get(R) || null, e, t, a, i, E)), !0;
        }
        case "gotpointercapture": {
          var w = l, V = w.pointerId;
          return ti.set(V, uc(ti.get(V) || null, e, t, a, i, w)), !0;
        }
      }
      return !1;
    }
    function Ap(e) {
      var t = bc(e.target);
      if (t !== null) {
        var a = qr(t);
        if (a !== null) {
          var i = a.tag;
          if (i === se) {
            var l = ji(a);
            if (l !== null) {
              e.blockedOn = l, Ff(e.priority, function() {
                Np(a);
              });
              return;
            }
          } else if (i === U) {
            var c = a.stateNode;
            if (Il(c)) {
              e.blockedOn = Io(a);
              return;
            }
          }
        }
      }
      e.blockedOn = null;
    }
    function im(e) {
      for (var t = Wu(), a = {
        blockedOn: null,
        target: e,
        priority: t
      }, i = 0; i < go.length && Op(t, go[i].priority); i++)
        ;
      go.splice(i, 0, a), i === 0 && Ap(a);
    }
    function sc(e) {
      if (e.blockedOn !== null)
        return !1;
      for (var t = e.targetContainers; t.length > 0; ) {
        var a = t[0], i = cc(e.domEventName, e.eventSystemFlags, a, e.nativeEvent);
        if (i === null) {
          var l = e.nativeEvent, c = new l.constructor(l.type, l);
          Lg(c), l.target.dispatchEvent(c), Us();
        } else {
          var p = ns(i);
          return p !== null && Xo(p), e.blockedOn = i, !1;
        }
        t.shift();
      }
      return !0;
    }
    function om(e, t, a) {
      sc(e) && a.delete(t);
    }
    function Hf() {
      jf = !1, Bi !== null && sc(Bi) && (Bi = null), Ii !== null && sc(Ii) && (Ii = null), An !== null && sc(An) && (An = null), Kr.forEach(om), ti.forEach(om);
    }
    function Yl(e, t) {
      e.blockedOn === t && (e.blockedOn = null, jf || (jf = !0, v.unstable_scheduleCallback(v.unstable_NormalPriority, Hf)));
    }
    function Br(e) {
      if (lc.length > 0) {
        Yl(lc[0], e);
        for (var t = 1; t < lc.length; t++) {
          var a = lc[t];
          a.blockedOn === e && (a.blockedOn = null);
        }
      }
      Bi !== null && Yl(Bi, e), Ii !== null && Yl(Ii, e), An !== null && Yl(An, e);
      var i = function(m) {
        return Yl(m, e);
      };
      Kr.forEach(i), ti.forEach(i);
      for (var l = 0; l < go.length; l++) {
        var c = go[l];
        c.blockedOn === e && (c.blockedOn = null);
      }
      for (; go.length > 0; ) {
        var p = go[0];
        if (p.blockedOn !== null)
          break;
        Ap(p), p.blockedOn === null && go.shift();
      }
    }
    var Mt = y.ReactCurrentBatchConfig, tr = !0;
    function In(e) {
      tr = !!e;
    }
    function kr() {
      return tr;
    }
    function Ua(e, t, a) {
      var i = Qu(t), l;
      switch (i) {
        case Sa:
          l = Gu;
          break;
        case ei:
          l = ur;
          break;
        case xr:
        default:
          l = Wl;
          break;
      }
      return l.bind(null, t, a, e);
    }
    function Gu(e, t, a, i) {
      var l = za(), c = Mt.transition;
      Mt.transition = null;
      try {
        lr(Sa), Wl(e, t, a, i);
      } finally {
        lr(l), Mt.transition = c;
      }
    }
    function ur(e, t, a, i) {
      var l = za(), c = Mt.transition;
      Mt.transition = null;
      try {
        lr(ei), Wl(e, t, a, i);
      } finally {
        lr(l), Mt.transition = c;
      }
    }
    function Wl(e, t, a, i) {
      tr && Gl(e, t, a, i);
    }
    function Gl(e, t, a, i) {
      var l = cc(e, t, a, i);
      if (l === null) {
        a0(e, t, i, Ql, a), Ti(e, i);
        return;
      }
      if (am(l, e, t, a, i)) {
        i.stopPropagation();
        return;
      }
      if (Ti(e, i), t & Ol && bi(e)) {
        for (; l !== null; ) {
          var c = ns(l);
          c !== null && qe(c);
          var p = cc(e, t, a, i);
          if (p === null && a0(e, t, i, Ql, a), p === l)
            break;
          l = p;
        }
        l !== null && i.stopPropagation();
        return;
      }
      a0(e, t, i, null, a);
    }
    var Ql = null;
    function cc(e, t, a, i) {
      Ql = null;
      var l = Xc(i), c = bc(l);
      if (c !== null) {
        var p = qr(c);
        if (p === null)
          c = null;
        else {
          var m = p.tag;
          if (m === se) {
            var E = ji(p);
            if (E !== null)
              return E;
            c = null;
          } else if (m === U) {
            var R = p.stateNode;
            if (Il(R))
              return Io(p);
            c = null;
          } else p !== c && (c = null);
        }
      }
      return Ql = c, null;
    }
    function Qu(e) {
      switch (e) {
        case "cancel":
        case "click":
        case "close":
        case "contextmenu":
        case "copy":
        case "cut":
        case "auxclick":
        case "dblclick":
        case "dragend":
        case "dragstart":
        case "drop":
        case "focusin":
        case "focusout":
        case "input":
        case "invalid":
        case "keydown":
        case "keypress":
        case "keyup":
        case "mousedown":
        case "mouseup":
        case "paste":
        case "pause":
        case "play":
        case "pointercancel":
        case "pointerdown":
        case "pointerup":
        case "ratechange":
        case "reset":
        case "resize":
        case "seeked":
        case "submit":
        case "touchcancel":
        case "touchend":
        case "touchstart":
        case "volumechange":
        case "change":
        case "selectionchange":
        case "textInput":
        case "compositionstart":
        case "compositionend":
        case "compositionupdate":
        case "beforeblur":
        case "afterblur":
        case "beforeinput":
        case "blur":
        case "fullscreenchange":
        case "focus":
        case "hashchange":
        case "popstate":
        case "select":
        case "selectstart":
          return Sa;
        case "drag":
        case "dragenter":
        case "dragexit":
        case "dragleave":
        case "dragover":
        case "mousemove":
        case "mouseout":
        case "mouseover":
        case "pointermove":
        case "pointerout":
        case "pointerover":
        case "scroll":
        case "toggle":
        case "touchmove":
        case "wheel":
        case "mouseenter":
        case "mouseleave":
        case "pointerenter":
        case "pointerleave":
          return ei;
        case "message": {
          var t = $h();
          switch (t) {
            case mo:
              return Sa;
            case Ys:
              return ei;
            case Ul:
            case Ws:
              return xr;
            case Uu:
              return Pf;
            default:
              return xr;
          }
        }
        default:
          return xr;
      }
    }
    function Ea(e, t, a) {
      return e.addEventListener(t, a, !1), a;
    }
    function Mp(e, t, a) {
      return e.addEventListener(t, a, !0), a;
    }
    function qu(e, t, a, i) {
      return e.addEventListener(t, a, {
        capture: !0,
        passive: i
      }), a;
    }
    function So(e, t, a, i) {
      return e.addEventListener(t, a, {
        passive: i
      }), a;
    }
    var Jo = null, fc = null, ni = null;
    function Vf(e) {
      return Jo = e, fc = Ku(), !0;
    }
    function Zo() {
      Jo = null, fc = null, ni = null;
    }
    function dc() {
      if (ni)
        return ni;
      var e, t = fc, a = t.length, i, l = Ku(), c = l.length;
      for (e = 0; e < a && t[e] === l[e]; e++)
        ;
      var p = a - e;
      for (i = 1; i <= p && t[a - i] === l[c - i]; i++)
        ;
      var m = i > 1 ? 1 - i : void 0;
      return ni = l.slice(e, m), ni;
    }
    function Ku() {
      return "value" in Jo ? Jo.value : Jo.textContent;
    }
    function Xu(e) {
      var t, a = e.keyCode;
      return "charCode" in e ? (t = e.charCode, t === 0 && a === 13 && (t = 13)) : t = a, t === 10 && (t = 13), t >= 32 || t === 13 ? t : 0;
    }
    function ql() {
      return !0;
    }
    function pc() {
      return !1;
    }
    function yn(e) {
      function t(a, i, l, c, p) {
        this._reactName = a, this._targetInst = l, this.type = i, this.nativeEvent = c, this.target = p, this.currentTarget = null;
        for (var m in e)
          if (e.hasOwnProperty(m)) {
            var E = e[m];
            E ? this[m] = E(c) : this[m] = c[m];
          }
        var R = c.defaultPrevented != null ? c.defaultPrevented : c.returnValue === !1;
        return R ? this.isDefaultPrevented = ql : this.isDefaultPrevented = pc, this.isPropagationStopped = pc, this;
      }
      return Et(t.prototype, {
        preventDefault: function() {
          this.defaultPrevented = !0;
          var a = this.nativeEvent;
          a && (a.preventDefault ? a.preventDefault() : typeof a.returnValue != "unknown" && (a.returnValue = !1), this.isDefaultPrevented = ql);
        },
        stopPropagation: function() {
          var a = this.nativeEvent;
          a && (a.stopPropagation ? a.stopPropagation() : typeof a.cancelBubble != "unknown" && (a.cancelBubble = !0), this.isPropagationStopped = ql);
        },
        /**
         * We release all dispatched `SyntheticEvent`s after each event loop, adding
         * them back into the pool. This allows a way to hold onto a reference that
         * won't be added back into the pool.
         */
        persist: function() {
        },
        /**
         * Checks if this event should be released back into the pool.
         *
         * @return {boolean} True if this should not be released, false otherwise.
         */
        isPersistent: ql
      }), t;
    }
    var Pa = {
      eventPhase: 0,
      bubbles: 0,
      cancelable: 0,
      timeStamp: function(e) {
        return e.timeStamp || Date.now();
      },
      defaultPrevented: 0,
      isTrusted: 0
    }, $a = yn(Pa), Sr = Et({}, Pa, {
      view: 0,
      detail: 0
    }), lm = yn(Sr), vc, hc, mc;
    function el(e) {
      e !== mc && (mc && e.type === "mousemove" ? (vc = e.screenX - mc.screenX, hc = e.screenY - mc.screenY) : (vc = 0, hc = 0), mc = e);
    }
    var yc = Et({}, Sr, {
      screenX: 0,
      screenY: 0,
      clientX: 0,
      clientY: 0,
      pageX: 0,
      pageY: 0,
      ctrlKey: 0,
      shiftKey: 0,
      altKey: 0,
      metaKey: 0,
      getModifierState: Pp,
      button: 0,
      buttons: 0,
      relatedTarget: function(e) {
        return e.relatedTarget === void 0 ? e.fromElement === e.srcElement ? e.toElement : e.fromElement : e.relatedTarget;
      },
      movementX: function(e) {
        return "movementX" in e ? e.movementX : (el(e), vc);
      },
      movementY: function(e) {
        return "movementY" in e ? e.movementY : hc;
      }
    }), Bf = yn(yc), Kl = Et({}, yc, {
      dataTransfer: 0
    }), Lp = yn(Kl), Xl = Et({}, Sr, {
      relatedTarget: 0
    }), If = yn(Xl), um = Et({}, Pa, {
      animationName: 0,
      elapsedTime: 0,
      pseudoElement: 0
    }), zp = yn(um), Yf = Et({}, Pa, {
      clipboardData: function(e) {
        return "clipboardData" in e ? e.clipboardData : window.clipboardData;
      }
    }), Vg = yn(Yf), Bg = Et({}, Pa, {
      data: 0
    }), Up = yn(Bg), sm = Up, Jl = {
      Esc: "Escape",
      Spacebar: " ",
      Left: "ArrowLeft",
      Up: "ArrowUp",
      Right: "ArrowRight",
      Down: "ArrowDown",
      Del: "Delete",
      Win: "OS",
      Menu: "ContextMenu",
      Apps: "ContextMenu",
      Scroll: "ScrollLock",
      MozPrintableKey: "Unidentified"
    }, Ig = {
      8: "Backspace",
      9: "Tab",
      12: "Clear",
      13: "Enter",
      16: "Shift",
      17: "Control",
      18: "Alt",
      19: "Pause",
      20: "CapsLock",
      27: "Escape",
      32: " ",
      33: "PageUp",
      34: "PageDown",
      35: "End",
      36: "Home",
      37: "ArrowLeft",
      38: "ArrowUp",
      39: "ArrowRight",
      40: "ArrowDown",
      45: "Insert",
      46: "Delete",
      112: "F1",
      113: "F2",
      114: "F3",
      115: "F4",
      116: "F5",
      117: "F6",
      118: "F7",
      119: "F8",
      120: "F9",
      121: "F10",
      122: "F11",
      123: "F12",
      144: "NumLock",
      145: "ScrollLock",
      224: "Meta"
    };
    function Ju(e) {
      if (e.key) {
        var t = Jl[e.key] || e.key;
        if (t !== "Unidentified")
          return t;
      }
      if (e.type === "keypress") {
        var a = Xu(e);
        return a === 13 ? "Enter" : String.fromCharCode(a);
      }
      return e.type === "keydown" || e.type === "keyup" ? Ig[e.keyCode] || "Unidentified" : "";
    }
    var cm = {
      Alt: "altKey",
      Control: "ctrlKey",
      Meta: "metaKey",
      Shift: "shiftKey"
    };
    function Pn(e) {
      var t = this, a = t.nativeEvent;
      if (a.getModifierState)
        return a.getModifierState(e);
      var i = cm[e];
      return i ? !!a[i] : !1;
    }
    function Pp(e) {
      return Pn;
    }
    var fm = Et({}, Sr, {
      key: Ju,
      code: 0,
      location: 0,
      ctrlKey: 0,
      shiftKey: 0,
      altKey: 0,
      metaKey: 0,
      repeat: 0,
      locale: 0,
      getModifierState: Pp,
      // Legacy Interface
      charCode: function(e) {
        return e.type === "keypress" ? Xu(e) : 0;
      },
      keyCode: function(e) {
        return e.type === "keydown" || e.type === "keyup" ? e.keyCode : 0;
      },
      which: function(e) {
        return e.type === "keypress" ? Xu(e) : e.type === "keydown" || e.type === "keyup" ? e.keyCode : 0;
      }
    }), Yg = yn(fm), Wg = Et({}, yc, {
      pointerId: 0,
      width: 0,
      height: 0,
      pressure: 0,
      tangentialPressure: 0,
      tiltX: 0,
      tiltY: 0,
      twist: 0,
      pointerType: 0,
      isPrimary: 0
    }), $p = yn(Wg), dm = Et({}, Sr, {
      touches: 0,
      targetTouches: 0,
      changedTouches: 0,
      altKey: 0,
      metaKey: 0,
      ctrlKey: 0,
      shiftKey: 0,
      getModifierState: Pp
    }), Gg = yn(dm), ri = Et({}, Pa, {
      propertyName: 0,
      elapsedTime: 0,
      pseudoElement: 0
    }), Fp = yn(ri), Qg = Et({}, yc, {
      deltaX: function(e) {
        return "deltaX" in e ? e.deltaX : (
          // Fallback to `wheelDeltaX` for Webkit and normalize (right is positive).
          "wheelDeltaX" in e ? -e.wheelDeltaX : 0
        );
      },
      deltaY: function(e) {
        return "deltaY" in e ? e.deltaY : (
          // Fallback to `wheelDeltaY` for Webkit and normalize (down is positive).
          "wheelDeltaY" in e ? -e.wheelDeltaY : (
            // Fallback to `wheelDelta` for IE<9 and normalize (down is positive).
            "wheelDelta" in e ? -e.wheelDelta : 0
          )
        );
      },
      deltaZ: 0,
      // Browsers without "deltaMode" is reporting in raw wheel delta where one
      // notch on the scroll is always +/- 120, roughly equivalent to pixels.
      // A good approximation of DOM_DELTA_LINE (1) is 5% of viewport size or
      // ~40 pixels, for DOM_DELTA_SCREEN (2) it is 87.5% of viewport size.
      deltaMode: 0
    }), tl = yn(Qg), Wf = [9, 13, 27, 32], nl = 229, Zu = Ht && "CompositionEvent" in window, Zl = null;
    Ht && "documentMode" in document && (Zl = document.documentMode);
    var jp = Ht && "TextEvent" in window && !Zl, pm = Ht && (!Zu || Zl && Zl > 8 && Zl <= 11), Gf = 32, vm = String.fromCharCode(Gf);
    function hm() {
      et("onBeforeInput", ["compositionend", "keypress", "textInput", "paste"]), et("onCompositionEnd", ["compositionend", "focusout", "keydown", "keypress", "keyup", "mousedown"]), et("onCompositionStart", ["compositionstart", "focusout", "keydown", "keypress", "keyup", "mousedown"]), et("onCompositionUpdate", ["compositionupdate", "focusout", "keydown", "keypress", "keyup", "mousedown"]);
    }
    var Hp = !1;
    function Qf(e) {
      return (e.ctrlKey || e.altKey || e.metaKey) && // ctrlKey && altKey is equivalent to AltGr, and is not a command.
      !(e.ctrlKey && e.altKey);
    }
    function qf(e) {
      switch (e) {
        case "compositionstart":
          return "onCompositionStart";
        case "compositionend":
          return "onCompositionEnd";
        case "compositionupdate":
          return "onCompositionUpdate";
      }
    }
    function mm(e, t) {
      return e === "keydown" && t.keyCode === nl;
    }
    function Kf(e, t) {
      switch (e) {
        case "keyup":
          return Wf.indexOf(t.keyCode) !== -1;
        case "keydown":
          return t.keyCode !== nl;
        case "keypress":
        case "mousedown":
        case "focusout":
          return !0;
        default:
          return !1;
      }
    }
    function ym(e) {
      var t = e.detail;
      return typeof t == "object" && "data" in t ? t.data : null;
    }
    function Vp(e) {
      return e.locale === "ko";
    }
    var rl = !1;
    function Xf(e, t, a, i, l) {
      var c, p;
      if (Zu ? c = qf(t) : rl ? Kf(t, i) && (c = "onCompositionEnd") : mm(t, i) && (c = "onCompositionStart"), !c)
        return null;
      pm && !Vp(i) && (!rl && c === "onCompositionStart" ? rl = Vf(l) : c === "onCompositionEnd" && rl && (p = dc()));
      var m = Tm(a, c);
      if (m.length > 0) {
        var E = new Up(c, t, null, i, l);
        if (e.push({
          event: E,
          listeners: m
        }), p)
          E.data = p;
        else {
          var R = ym(i);
          R !== null && (E.data = R);
        }
      }
    }
    function Bp(e, t) {
      switch (e) {
        case "compositionend":
          return ym(t);
        case "keypress":
          var a = t.which;
          return a !== Gf ? null : (Hp = !0, vm);
        case "textInput":
          var i = t.data;
          return i === vm && Hp ? null : i;
        default:
          return null;
      }
    }
    function Jf(e, t) {
      if (rl) {
        if (e === "compositionend" || !Zu && Kf(e, t)) {
          var a = dc();
          return Zo(), rl = !1, a;
        }
        return null;
      }
      switch (e) {
        case "paste":
          return null;
        case "keypress":
          if (!Qf(t)) {
            if (t.char && t.char.length > 1)
              return t.char;
            if (t.which)
              return String.fromCharCode(t.which);
          }
          return null;
        case "compositionend":
          return pm && !Vp(t) ? null : t.data;
        default:
          return null;
      }
    }
    function gm(e, t, a, i, l) {
      var c;
      if (jp ? c = Bp(t, i) : c = Jf(t, i), !c)
        return null;
      var p = Tm(a, "onBeforeInput");
      if (p.length > 0) {
        var m = new sm("onBeforeInput", "beforeinput", null, i, l);
        e.push({
          event: m,
          listeners: p
        }), m.data = c;
      }
    }
    function qg(e, t, a, i, l, c, p) {
      Xf(e, t, a, i, l), gm(e, t, a, i, l);
    }
    var Zf = {
      color: !0,
      date: !0,
      datetime: !0,
      "datetime-local": !0,
      email: !0,
      month: !0,
      number: !0,
      password: !0,
      range: !0,
      search: !0,
      tel: !0,
      text: !0,
      time: !0,
      url: !0,
      week: !0
    };
    function Sm(e) {
      var t = e && e.nodeName && e.nodeName.toLowerCase();
      return t === "input" ? !!Zf[e.type] : t === "textarea";
    }
    /**
     * Checks if an event is supported in the current execution environment.
     *
     * NOTE: This will not work correctly for non-generic events such as `change`,
     * `reset`, `load`, `error`, and `select`.
     *
     * Borrows from Modernizr.
     *
     * @param {string} eventNameSuffix Event name, e.g. "click".
     * @return {boolean} True if the event is supported.
     * @internal
     * @license Modernizr 3.0.0pre (Custom Build) | MIT
     */
    function gc(e) {
      if (!Ht)
        return !1;
      var t = "on" + e, a = t in document;
      if (!a) {
        var i = document.createElement("div");
        i.setAttribute(t, "return;"), a = typeof i[t] == "function";
      }
      return a;
    }
    function Kg() {
      et("onChange", ["change", "click", "focusin", "focusout", "input", "keydown", "keyup", "selectionchange"]);
    }
    function Sc(e, t, a, i) {
      ep(i);
      var l = Tm(t, "onChange");
      if (l.length > 0) {
        var c = new $a("onChange", "change", null, a, i);
        e.push({
          event: c,
          listeners: l
        });
      }
    }
    var n = null, r = null;
    function o(e) {
      var t = e.nodeName && e.nodeName.toLowerCase();
      return t === "select" || t === "input" && e.type === "file";
    }
    function s(e) {
      var t = [];
      Sc(t, r, e, Xc(e)), Ah(d, t);
    }
    function d(e) {
      FC(e, 0);
    }
    function h(e) {
      var t = id(e);
      if (zo(t))
        return e;
    }
    function b(e, t) {
      if (e === "change")
        return t;
    }
    var O = !1;
    Ht && (O = gc("input") && (!document.documentMode || document.documentMode > 9));
    function P(e, t) {
      n = e, r = t, n.attachEvent("onpropertychange", ve);
    }
    function J() {
      n && (n.detachEvent("onpropertychange", ve), n = null, r = null);
    }
    function ve(e) {
      e.propertyName === "value" && h(r) && s(e);
    }
    function he(e, t, a) {
      e === "focusin" ? (J(), P(t, a)) : e === "focusout" && J();
    }
    function pe(e, t) {
      if (e === "selectionchange" || e === "keyup" || e === "keydown")
        return h(r);
    }
    function Ve(e) {
      var t = e.nodeName;
      return t && t.toLowerCase() === "input" && (e.type === "checkbox" || e.type === "radio");
    }
    function Xe(e, t) {
      if (e === "click")
        return h(t);
    }
    function Ze(e, t) {
      if (e === "input" || e === "change")
        return h(t);
    }
    function Yn(e) {
      var t = e._wrapperState;
      !t || !t.controlled || e.type !== "number" || Ke(e, "number", e.value);
    }
    function Y(e, t, a, i, l, c, p) {
      var m = a ? id(a) : window, E, R;
      if (o(m) ? E = b : Sm(m) ? O ? E = Ze : (E = pe, R = he) : Ve(m) && (E = Xe), E) {
        var w = E(t, a);
        if (w) {
          Sc(e, w, i, l);
          return;
        }
      }
      R && R(t, m, a), t === "focusout" && Yn(m);
    }
    function H() {
      ut("onMouseEnter", ["mouseout", "mouseover"]), ut("onMouseLeave", ["mouseout", "mouseover"]), ut("onPointerEnter", ["pointerout", "pointerover"]), ut("onPointerLeave", ["pointerout", "pointerover"]);
    }
    function Q(e, t, a, i, l, c, p) {
      var m = t === "mouseover" || t === "pointerover", E = t === "mouseout" || t === "pointerout";
      if (m && !zg(i)) {
        var R = i.relatedTarget || i.fromElement;
        if (R && (bc(R) || rv(R)))
          return;
      }
      if (!(!E && !m)) {
        var w;
        if (l.window === l)
          w = l;
        else {
          var V = l.ownerDocument;
          V ? w = V.defaultView || V.parentWindow : w = window;
        }
        var $, X;
        if (E) {
          var Z = i.relatedTarget || i.toElement;
          if ($ = a, X = Z ? bc(Z) : null, X !== null) {
            var ne = qr(X);
            (X !== ne || X.tag !== B && X.tag !== M) && (X = null);
          }
        } else
          $ = null, X = a;
        if ($ !== X) {
          var Me = Bf, lt = "onMouseLeave", tt = "onMouseEnter", jt = "mouse";
          (t === "pointerout" || t === "pointerover") && (Me = $p, lt = "onPointerLeave", tt = "onPointerEnter", jt = "pointer");
          var Lt = $ == null ? w : id($), W = X == null ? w : id(X), re = new Me(lt, jt + "leave", $, i, l);
          re.target = Lt, re.relatedTarget = W;
          var G = null, me = bc(l);
          if (me === a) {
            var We = new Me(tt, jt + "enter", X, i, l);
            We.target = W, We.relatedTarget = Lt, G = We;
          }
          tx(e, re, G, $, X);
        }
      }
    }
    function Se(e, t) {
      return e === t && (e !== 0 || 1 / e === 1 / t) || e !== e && t !== t;
    }
    var $e = typeof Object.is == "function" ? Object.is : Se;
    function at(e, t) {
      if ($e(e, t))
        return !0;
      if (typeof e != "object" || e === null || typeof t != "object" || t === null)
        return !1;
      var a = Object.keys(e), i = Object.keys(t);
      if (a.length !== i.length)
        return !1;
      for (var l = 0; l < a.length; l++) {
        var c = a[l];
        if (!Te.call(t, c) || !$e(e[c], t[c]))
          return !1;
      }
      return !0;
    }
    function st(e) {
      for (; e && e.firstChild; )
        e = e.firstChild;
      return e;
    }
    function mt(e) {
      for (; e; ) {
        if (e.nextSibling)
          return e.nextSibling;
        e = e.parentNode;
      }
    }
    function sr(e, t) {
      for (var a = st(e), i = 0, l = 0; a; ) {
        if (a.nodeType === fo) {
          if (l = i + a.textContent.length, i <= t && l >= t)
            return {
              node: a,
              offset: t - i
            };
          i = l;
        }
        a = st(mt(a));
      }
    }
    function Bt(e) {
      var t = e.ownerDocument, a = t && t.defaultView || window, i = a.getSelection && a.getSelection();
      if (!i || i.rangeCount === 0)
        return null;
      var l = i.anchorNode, c = i.anchorOffset, p = i.focusNode, m = i.focusOffset;
      try {
        l.nodeType, p.nodeType;
      } catch {
        return null;
      }
      return al(e, l, c, p, m);
    }
    function al(e, t, a, i, l) {
      var c = 0, p = -1, m = -1, E = 0, R = 0, w = e, V = null;
      e: for (; ; ) {
        for (var $ = null; w === t && (a === 0 || w.nodeType === fo) && (p = c + a), w === i && (l === 0 || w.nodeType === fo) && (m = c + l), w.nodeType === fo && (c += w.nodeValue.length), ($ = w.firstChild) !== null; )
          V = w, w = $;
        for (; ; ) {
          if (w === e)
            break e;
          if (V === t && ++E === a && (p = c), V === i && ++R === l && (m = c), ($ = w.nextSibling) !== null)
            break;
          w = V, V = w.parentNode;
        }
        w = $;
      }
      return p === -1 || m === -1 ? null : {
        start: p,
        end: m
      };
    }
    function Xg(e, t) {
      var a = e.ownerDocument || document, i = a && a.defaultView || window;
      if (i.getSelection) {
        var l = i.getSelection(), c = e.textContent.length, p = Math.min(t.start, c), m = t.end === void 0 ? p : Math.min(t.end, c);
        if (!l.extend && p > m) {
          var E = m;
          m = p, p = E;
        }
        var R = sr(e, p), w = sr(e, m);
        if (R && w) {
          if (l.rangeCount === 1 && l.anchorNode === R.node && l.anchorOffset === R.offset && l.focusNode === w.node && l.focusOffset === w.offset)
            return;
          var V = a.createRange();
          V.setStart(R.node, R.offset), l.removeAllRanges(), p > m ? (l.addRange(V), l.extend(w.node, w.offset)) : (V.setEnd(w.node, w.offset), l.addRange(V));
        }
      }
    }
    function _C(e) {
      return e && e.nodeType === fo;
    }
    function kC(e, t) {
      return !e || !t ? !1 : e === t ? !0 : _C(e) ? !1 : _C(t) ? kC(e, t.parentNode) : "contains" in e ? e.contains(t) : e.compareDocumentPosition ? !!(e.compareDocumentPosition(t) & 16) : !1;
    }
    function Pw(e) {
      return e && e.ownerDocument && kC(e.ownerDocument.documentElement, e);
    }
    function $w(e) {
      try {
        return typeof e.contentWindow.location.href == "string";
      } catch {
        return !1;
      }
    }
    function OC() {
      for (var e = window, t = uo(); t instanceof e.HTMLIFrameElement; ) {
        if ($w(t))
          e = t.contentWindow;
        else
          return t;
        t = uo(e.document);
      }
      return t;
    }
    function Jg(e) {
      var t = e && e.nodeName && e.nodeName.toLowerCase();
      return t && (t === "input" && (e.type === "text" || e.type === "search" || e.type === "tel" || e.type === "url" || e.type === "password") || t === "textarea" || e.contentEditable === "true");
    }
    function Fw() {
      var e = OC();
      return {
        focusedElem: e,
        selectionRange: Jg(e) ? Hw(e) : null
      };
    }
    function jw(e) {
      var t = OC(), a = e.focusedElem, i = e.selectionRange;
      if (t !== a && Pw(a)) {
        i !== null && Jg(a) && Vw(a, i);
        for (var l = [], c = a; c = c.parentNode; )
          c.nodeType === da && l.push({
            element: c,
            left: c.scrollLeft,
            top: c.scrollTop
          });
        typeof a.focus == "function" && a.focus();
        for (var p = 0; p < l.length; p++) {
          var m = l[p];
          m.element.scrollLeft = m.left, m.element.scrollTop = m.top;
        }
      }
    }
    function Hw(e) {
      var t;
      return "selectionStart" in e ? t = {
        start: e.selectionStart,
        end: e.selectionEnd
      } : t = Bt(e), t || {
        start: 0,
        end: 0
      };
    }
    function Vw(e, t) {
      var a = t.start, i = t.end;
      i === void 0 && (i = a), "selectionStart" in e ? (e.selectionStart = a, e.selectionEnd = Math.min(i, e.value.length)) : Xg(e, t);
    }
    var Bw = Ht && "documentMode" in document && document.documentMode <= 11;
    function Iw() {
      et("onSelect", ["focusout", "contextmenu", "dragend", "focusin", "keydown", "keyup", "mousedown", "mouseup", "selectionchange"]);
    }
    var ed = null, Zg = null, Ip = null, e0 = !1;
    function Yw(e) {
      if ("selectionStart" in e && Jg(e))
        return {
          start: e.selectionStart,
          end: e.selectionEnd
        };
      var t = e.ownerDocument && e.ownerDocument.defaultView || window, a = t.getSelection();
      return {
        anchorNode: a.anchorNode,
        anchorOffset: a.anchorOffset,
        focusNode: a.focusNode,
        focusOffset: a.focusOffset
      };
    }
    function Ww(e) {
      return e.window === e ? e.document : e.nodeType === po ? e : e.ownerDocument;
    }
    function DC(e, t, a) {
      var i = Ww(a);
      if (!(e0 || ed == null || ed !== uo(i))) {
        var l = Yw(ed);
        if (!Ip || !at(Ip, l)) {
          Ip = l;
          var c = Tm(Zg, "onSelect");
          if (c.length > 0) {
            var p = new $a("onSelect", "select", null, t, a);
            e.push({
              event: p,
              listeners: c
            }), p.target = ed;
          }
        }
      }
    }
    function Gw(e, t, a, i, l, c, p) {
      var m = a ? id(a) : window;
      switch (t) {
        case "focusin":
          (Sm(m) || m.contentEditable === "true") && (ed = m, Zg = a, Ip = null);
          break;
        case "focusout":
          ed = null, Zg = null, Ip = null;
          break;
        case "mousedown":
          e0 = !0;
          break;
        case "contextmenu":
        case "mouseup":
        case "dragend":
          e0 = !1, DC(e, i, l);
          break;
        case "selectionchange":
          if (Bw)
            break;
        case "keydown":
        case "keyup":
          DC(e, i, l);
      }
    }
    function Em(e, t) {
      var a = {};
      return a[e.toLowerCase()] = t.toLowerCase(), a["Webkit" + e] = "webkit" + t, a["Moz" + e] = "moz" + t, a;
    }
    var td = {
      animationend: Em("Animation", "AnimationEnd"),
      animationiteration: Em("Animation", "AnimationIteration"),
      animationstart: Em("Animation", "AnimationStart"),
      transitionend: Em("Transition", "TransitionEnd")
    }, t0 = {}, NC = {};
    Ht && (NC = document.createElement("div").style, "AnimationEvent" in window || (delete td.animationend.animation, delete td.animationiteration.animation, delete td.animationstart.animation), "TransitionEvent" in window || delete td.transitionend.transition);
    function Cm(e) {
      if (t0[e])
        return t0[e];
      if (!td[e])
        return e;
      var t = td[e];
      for (var a in t)
        if (t.hasOwnProperty(a) && a in NC)
          return t0[e] = t[a];
      return e;
    }
    var AC = Cm("animationend"), MC = Cm("animationiteration"), LC = Cm("animationstart"), zC = Cm("transitionend"), UC = /* @__PURE__ */ new Map(), PC = ["abort", "auxClick", "cancel", "canPlay", "canPlayThrough", "click", "close", "contextMenu", "copy", "cut", "drag", "dragEnd", "dragEnter", "dragExit", "dragLeave", "dragOver", "dragStart", "drop", "durationChange", "emptied", "encrypted", "ended", "error", "gotPointerCapture", "input", "invalid", "keyDown", "keyPress", "keyUp", "load", "loadedData", "loadedMetadata", "loadStart", "lostPointerCapture", "mouseDown", "mouseMove", "mouseOut", "mouseOver", "mouseUp", "paste", "pause", "play", "playing", "pointerCancel", "pointerDown", "pointerMove", "pointerOut", "pointerOver", "pointerUp", "progress", "rateChange", "reset", "resize", "seeked", "seeking", "stalled", "submit", "suspend", "timeUpdate", "touchCancel", "touchEnd", "touchStart", "volumeChange", "scroll", "toggle", "touchMove", "waiting", "wheel"];
    function es(e, t) {
      UC.set(e, t), et(t, [e]);
    }
    function Qw() {
      for (var e = 0; e < PC.length; e++) {
        var t = PC[e], a = t.toLowerCase(), i = t[0].toUpperCase() + t.slice(1);
        es(a, "on" + i);
      }
      es(AC, "onAnimationEnd"), es(MC, "onAnimationIteration"), es(LC, "onAnimationStart"), es("dblclick", "onDoubleClick"), es("focusin", "onFocus"), es("focusout", "onBlur"), es(zC, "onTransitionEnd");
    }
    function qw(e, t, a, i, l, c, p) {
      var m = UC.get(t);
      if (m !== void 0) {
        var E = $a, R = t;
        switch (t) {
          case "keypress":
            if (Xu(i) === 0)
              return;
          case "keydown":
          case "keyup":
            E = Yg;
            break;
          case "focusin":
            R = "focus", E = If;
            break;
          case "focusout":
            R = "blur", E = If;
            break;
          case "beforeblur":
          case "afterblur":
            E = If;
            break;
          case "click":
            if (i.button === 2)
              return;
          case "auxclick":
          case "dblclick":
          case "mousedown":
          case "mousemove":
          case "mouseup":
          case "mouseout":
          case "mouseover":
          case "contextmenu":
            E = Bf;
            break;
          case "drag":
          case "dragend":
          case "dragenter":
          case "dragexit":
          case "dragleave":
          case "dragover":
          case "dragstart":
          case "drop":
            E = Lp;
            break;
          case "touchcancel":
          case "touchend":
          case "touchmove":
          case "touchstart":
            E = Gg;
            break;
          case AC:
          case MC:
          case LC:
            E = zp;
            break;
          case zC:
            E = Fp;
            break;
          case "scroll":
            E = lm;
            break;
          case "wheel":
            E = tl;
            break;
          case "copy":
          case "cut":
          case "paste":
            E = Vg;
            break;
          case "gotpointercapture":
          case "lostpointercapture":
          case "pointercancel":
          case "pointerdown":
          case "pointermove":
          case "pointerout":
          case "pointerover":
          case "pointerup":
            E = $p;
            break;
        }
        var w = (c & Ol) !== 0;
        {
          var V = !w && // TODO: ideally, we'd eventually add all events from
          // nonDelegatedEvents list in DOMPluginEventSystem.
          // Then we can remove this special list.
          // This is a breaking change that can wait until React 18.
          t === "scroll", $ = Zw(a, m, i.type, w, V);
          if ($.length > 0) {
            var X = new E(m, R, null, i, l);
            e.push({
              event: X,
              listeners: $
            });
          }
        }
      }
    }
    Qw(), H(), Kg(), Iw(), hm();
    function Kw(e, t, a, i, l, c, p) {
      qw(e, t, a, i, l, c);
      var m = (c & Zd) === 0;
      m && (Q(e, t, a, i, l), Y(e, t, a, i, l), Gw(e, t, a, i, l), qg(e, t, a, i, l));
    }
    var Yp = ["abort", "canplay", "canplaythrough", "durationchange", "emptied", "encrypted", "ended", "error", "loadeddata", "loadedmetadata", "loadstart", "pause", "play", "playing", "progress", "ratechange", "resize", "seeked", "seeking", "stalled", "suspend", "timeupdate", "volumechange", "waiting"], n0 = new Set(["cancel", "close", "invalid", "load", "scroll", "toggle"].concat(Yp));
    function $C(e, t, a) {
      var i = e.type || "unknown-event";
      e.currentTarget = a, Hs(i, t, void 0, e), e.currentTarget = null;
    }
    function Xw(e, t, a) {
      var i;
      if (a)
        for (var l = t.length - 1; l >= 0; l--) {
          var c = t[l], p = c.instance, m = c.currentTarget, E = c.listener;
          if (p !== i && e.isPropagationStopped())
            return;
          $C(e, E, m), i = p;
        }
      else
        for (var R = 0; R < t.length; R++) {
          var w = t[R], V = w.instance, $ = w.currentTarget, X = w.listener;
          if (V !== i && e.isPropagationStopped())
            return;
          $C(e, X, $), i = V;
        }
    }
    function FC(e, t) {
      for (var a = (t & Ol) !== 0, i = 0; i < e.length; i++) {
        var l = e[i], c = l.event, p = l.listeners;
        Xw(c, p, a);
      }
      vo();
    }
    function Jw(e, t, a, i, l) {
      var c = Xc(a), p = [];
      Kw(p, e, i, a, c, t), FC(p, t);
    }
    function Mn(e, t) {
      n0.has(e) || g('Did not expect a listenToNonDelegatedEvent() call for "%s". This is a bug in React. Please file an issue.', e);
      var a = !1, i = k_(t), l = nx(e);
      i.has(l) || (jC(t, e, $i, a), i.add(l));
    }
    function r0(e, t, a) {
      n0.has(e) && !t && g('Did not expect a listenToNativeEvent() call for "%s" in the bubble phase. This is a bug in React. Please file an issue.', e);
      var i = 0;
      t && (i |= Ol), jC(a, e, i, t);
    }
    var bm = "_reactListening" + Math.random().toString(36).slice(2);
    function Wp(e) {
      if (!e[bm]) {
        e[bm] = !0, ze.forEach(function(a) {
          a !== "selectionchange" && (n0.has(a) || r0(a, !1, e), r0(a, !0, e));
        });
        var t = e.nodeType === po ? e : e.ownerDocument;
        t !== null && (t[bm] || (t[bm] = !0, r0("selectionchange", !1, t)));
      }
    }
    function jC(e, t, a, i, l) {
      var c = Ua(e, t, a), p = void 0;
      js && (t === "touchstart" || t === "touchmove" || t === "wheel") && (p = !0), e = e, i ? p !== void 0 ? qu(e, t, c, p) : Mp(e, t, c) : p !== void 0 ? So(e, t, c, p) : Ea(e, t, c);
    }
    function HC(e, t) {
      return e === t || e.nodeType === qn && e.parentNode === t;
    }
    function a0(e, t, a, i, l) {
      var c = i;
      if (!(t & Jd) && !(t & $i)) {
        var p = l;
        if (i !== null) {
          var m = i;
          e: for (; ; ) {
            if (m === null)
              return;
            var E = m.tag;
            if (E === U || E === te) {
              var R = m.stateNode.containerInfo;
              if (HC(R, p))
                break;
              if (E === te)
                for (var w = m.return; w !== null; ) {
                  var V = w.tag;
                  if (V === U || V === te) {
                    var $ = w.stateNode.containerInfo;
                    if (HC($, p))
                      return;
                  }
                  w = w.return;
                }
              for (; R !== null; ) {
                var X = bc(R);
                if (X === null)
                  return;
                var Z = X.tag;
                if (Z === B || Z === M) {
                  m = c = X;
                  continue e;
                }
                R = R.parentNode;
              }
            }
            m = m.return;
          }
        }
      }
      Ah(function() {
        return Jw(e, t, a, c);
      });
    }
    function Gp(e, t, a) {
      return {
        instance: e,
        listener: t,
        currentTarget: a
      };
    }
    function Zw(e, t, a, i, l, c) {
      for (var p = t !== null ? t + "Capture" : null, m = i ? p : t, E = [], R = e, w = null; R !== null; ) {
        var V = R, $ = V.stateNode, X = V.tag;
        if (X === B && $ !== null && (w = $, m !== null)) {
          var Z = Nl(R, m);
          Z != null && E.push(Gp(R, Z, w));
        }
        if (l)
          break;
        R = R.return;
      }
      return E;
    }
    function Tm(e, t) {
      for (var a = t + "Capture", i = [], l = e; l !== null; ) {
        var c = l, p = c.stateNode, m = c.tag;
        if (m === B && p !== null) {
          var E = p, R = Nl(l, a);
          R != null && i.unshift(Gp(l, R, E));
          var w = Nl(l, t);
          w != null && i.push(Gp(l, w, E));
        }
        l = l.return;
      }
      return i;
    }
    function nd(e) {
      if (e === null)
        return null;
      do
        e = e.return;
      while (e && e.tag !== B);
      return e || null;
    }
    function ex(e, t) {
      for (var a = e, i = t, l = 0, c = a; c; c = nd(c))
        l++;
      for (var p = 0, m = i; m; m = nd(m))
        p++;
      for (; l - p > 0; )
        a = nd(a), l--;
      for (; p - l > 0; )
        i = nd(i), p--;
      for (var E = l; E--; ) {
        if (a === i || i !== null && a === i.alternate)
          return a;
        a = nd(a), i = nd(i);
      }
      return null;
    }
    function VC(e, t, a, i, l) {
      for (var c = t._reactName, p = [], m = a; m !== null && m !== i; ) {
        var E = m, R = E.alternate, w = E.stateNode, V = E.tag;
        if (R !== null && R === i)
          break;
        if (V === B && w !== null) {
          var $ = w;
          if (l) {
            var X = Nl(m, c);
            X != null && p.unshift(Gp(m, X, $));
          } else if (!l) {
            var Z = Nl(m, c);
            Z != null && p.push(Gp(m, Z, $));
          }
        }
        m = m.return;
      }
      p.length !== 0 && e.push({
        event: t,
        listeners: p
      });
    }
    function tx(e, t, a, i, l) {
      var c = i && l ? ex(i, l) : null;
      i !== null && VC(e, t, i, c, !1), l !== null && a !== null && VC(e, a, l, c, !0);
    }
    function nx(e, t) {
      return e + "__bubble";
    }
    var ai = !1, Qp = "dangerouslySetInnerHTML", Rm = "suppressContentEditableWarning", ts = "suppressHydrationWarning", BC = "autoFocus", Ec = "children", Cc = "style", wm = "__html", i0, xm, qp, IC, _m, YC, WC;
    i0 = {
      // There are working polyfills for <dialog>. Let people use it.
      dialog: !0,
      // Electron ships a custom <webview> tag to display external web content in
      // an isolated frame and process.
      // This tag is not present in non Electron environments such as JSDom which
      // is often used for testing purposes.
      // @see https://electronjs.org/docs/api/webview-tag
      webview: !0
    }, xm = function(e, t) {
      xh(e, t), Ou(e, t), Nh(e, t, {
        registrationNameDependencies: we,
        possibleRegistrationNames: Ye
      });
    }, YC = Ht && !document.documentMode, qp = function(e, t, a) {
      if (!ai) {
        var i = km(a), l = km(t);
        l !== i && (ai = !0, g("Prop `%s` did not match. Server: %s Client: %s", e, JSON.stringify(l), JSON.stringify(i)));
      }
    }, IC = function(e) {
      if (!ai) {
        ai = !0;
        var t = [];
        e.forEach(function(a) {
          t.push(a);
        }), g("Extra attributes from the server: %s", t);
      }
    }, _m = function(e, t) {
      t === !1 ? g("Expected `%s` listener to be a function, instead got `false`.\n\nIf you used to conditionally omit it with %s={condition && value}, pass %s={condition ? value : undefined} instead.", e, e, e) : g("Expected `%s` listener to be a function, instead got a value of `%s` type.", e, typeof t);
    }, WC = function(e, t) {
      var a = e.namespaceURI === mi ? e.ownerDocument.createElement(e.tagName) : e.ownerDocument.createElementNS(e.namespaceURI, e.tagName);
      return a.innerHTML = t, a.innerHTML;
    };
    var rx = /\r\n?/g, ax = /\u0000|\uFFFD/g;
    function km(e) {
      ir(e);
      var t = typeof e == "string" ? e : "" + e;
      return t.replace(rx, `
`).replace(ax, "");
    }
    function Om(e, t, a, i) {
      var l = km(t), c = km(e);
      if (c !== l && (i && (ai || (ai = !0, g('Text content did not match. Server: "%s" Client: "%s"', c, l))), a && ie))
        throw new Error("Text content does not match server-rendered HTML.");
    }
    function GC(e) {
      return e.nodeType === po ? e : e.ownerDocument;
    }
    function ix() {
    }
    function Dm(e) {
      e.onclick = ix;
    }
    function ox(e, t, a, i, l) {
      for (var c in i)
        if (i.hasOwnProperty(c)) {
          var p = i[c];
          if (c === Cc)
            p && Object.freeze(p), Ch(t, p);
          else if (c === Qp) {
            var m = p ? p[wm] : void 0;
            m != null && sh(t, m);
          } else if (c === Ec)
            if (typeof p == "string") {
              var E = e !== "textarea" || p !== "";
              E && Po(t, p);
            } else typeof p == "number" && Po(t, "" + p);
          else c === Rm || c === ts || c === BC || (we.hasOwnProperty(c) ? p != null && (typeof p != "function" && _m(c, p), c === "onScroll" && Mn("scroll", t)) : p != null && Da(t, c, p, l));
        }
    }
    function lx(e, t, a, i) {
      for (var l = 0; l < t.length; l += 2) {
        var c = t[l], p = t[l + 1];
        c === Cc ? Ch(e, p) : c === Qp ? sh(e, p) : c === Ec ? Po(e, p) : Da(e, c, p, i);
      }
    }
    function ux(e, t, a, i) {
      var l, c = GC(a), p, m = i;
      if (m === mi && (m = Wd(e)), m === mi) {
        if (l = $o(e, t), !l && e !== e.toLowerCase() && g("<%s /> is using incorrect casing. Use PascalCase for React components, or lowercase for HTML elements.", e), e === "script") {
          var E = c.createElement("div");
          E.innerHTML = "<script><\/script>";
          var R = E.firstChild;
          p = E.removeChild(R);
        } else if (typeof t.is == "string")
          p = c.createElement(e, {
            is: t.is
          });
        else if (p = c.createElement(e), e === "select") {
          var w = p;
          t.multiple ? w.multiple = !0 : t.size && (w.size = t.size);
        }
      } else
        p = c.createElementNS(m, e);
      return m === mi && !l && Object.prototype.toString.call(p) === "[object HTMLUnknownElement]" && !Te.call(i0, e) && (i0[e] = !0, g("The tag <%s> is unrecognized in this browser. If you meant to render a React component, start its name with an uppercase letter.", e)), p;
    }
    function sx(e, t) {
      return GC(t).createTextNode(e);
    }
    function cx(e, t, a, i) {
      var l = $o(t, a);
      xm(t, a);
      var c;
      switch (t) {
        case "dialog":
          Mn("cancel", e), Mn("close", e), c = a;
          break;
        case "iframe":
        case "object":
        case "embed":
          Mn("load", e), c = a;
          break;
        case "video":
        case "audio":
          for (var p = 0; p < Yp.length; p++)
            Mn(Yp[p], e);
          c = a;
          break;
        case "source":
          Mn("error", e), c = a;
          break;
        case "img":
        case "image":
        case "link":
          Mn("error", e), Mn("load", e), c = a;
          break;
        case "details":
          Mn("toggle", e), c = a;
          break;
        case "input":
          bu(e, a), c = qa(e, a), Mn("invalid", e);
          break;
        case "option":
          Kt(e, a), c = a;
          break;
        case "select":
          ks(e, a), c = kl(e, a), Mn("invalid", e);
          break;
        case "textarea":
          oh(e, a), c = Yc(e, a), Mn("invalid", e);
          break;
        default:
          c = a;
      }
      switch (qc(t, c), ox(t, e, i, c, l), t) {
        case "input":
          Qa(e), K(e, a, !1);
          break;
        case "textarea":
          Qa(e), uh(e);
          break;
        case "option":
          ln(e, a);
          break;
        case "select":
          Bd(e, a);
          break;
        default:
          typeof c.onClick == "function" && Dm(e);
          break;
      }
    }
    function fx(e, t, a, i, l) {
      xm(t, i);
      var c = null, p, m;
      switch (t) {
        case "input":
          p = qa(e, a), m = qa(e, i), c = [];
          break;
        case "select":
          p = kl(e, a), m = kl(e, i), c = [];
          break;
        case "textarea":
          p = Yc(e, a), m = Yc(e, i), c = [];
          break;
        default:
          p = a, m = i, typeof p.onClick != "function" && typeof m.onClick == "function" && Dm(e);
          break;
      }
      qc(t, m);
      var E, R, w = null;
      for (E in p)
        if (!(m.hasOwnProperty(E) || !p.hasOwnProperty(E) || p[E] == null))
          if (E === Cc) {
            var V = p[E];
            for (R in V)
              V.hasOwnProperty(R) && (w || (w = {}), w[R] = "");
          } else E === Qp || E === Ec || E === Rm || E === ts || E === BC || (we.hasOwnProperty(E) ? c || (c = []) : (c = c || []).push(E, null));
      for (E in m) {
        var $ = m[E], X = p != null ? p[E] : void 0;
        if (!(!m.hasOwnProperty(E) || $ === X || $ == null && X == null))
          if (E === Cc)
            if ($ && Object.freeze($), X) {
              for (R in X)
                X.hasOwnProperty(R) && (!$ || !$.hasOwnProperty(R)) && (w || (w = {}), w[R] = "");
              for (R in $)
                $.hasOwnProperty(R) && X[R] !== $[R] && (w || (w = {}), w[R] = $[R]);
            } else
              w || (c || (c = []), c.push(E, w)), w = $;
          else if (E === Qp) {
            var Z = $ ? $[wm] : void 0, ne = X ? X[wm] : void 0;
            Z != null && ne !== Z && (c = c || []).push(E, Z);
          } else E === Ec ? (typeof $ == "string" || typeof $ == "number") && (c = c || []).push(E, "" + $) : E === Rm || E === ts || (we.hasOwnProperty(E) ? ($ != null && (typeof $ != "function" && _m(E, $), E === "onScroll" && Mn("scroll", e)), !c && X !== $ && (c = [])) : (c = c || []).push(E, $));
      }
      return w && (yi(w, m[Cc]), (c = c || []).push(Cc, w)), c;
    }
    function dx(e, t, a, i, l) {
      a === "input" && l.type === "radio" && l.name != null && C(e, l);
      var c = $o(a, i), p = $o(a, l);
      switch (lx(e, t, c, p), a) {
        case "input":
          D(e, l);
          break;
        case "textarea":
          lh(e, l);
          break;
        case "select":
          Ic(e, l);
          break;
      }
    }
    function px(e) {
      {
        var t = e.toLowerCase();
        return xu.hasOwnProperty(t) && xu[t] || null;
      }
    }
    function vx(e, t, a, i, l, c, p) {
      var m, E;
      switch (m = $o(t, a), xm(t, a), t) {
        case "dialog":
          Mn("cancel", e), Mn("close", e);
          break;
        case "iframe":
        case "object":
        case "embed":
          Mn("load", e);
          break;
        case "video":
        case "audio":
          for (var R = 0; R < Yp.length; R++)
            Mn(Yp[R], e);
          break;
        case "source":
          Mn("error", e);
          break;
        case "img":
        case "image":
        case "link":
          Mn("error", e), Mn("load", e);
          break;
        case "details":
          Mn("toggle", e);
          break;
        case "input":
          bu(e, a), Mn("invalid", e);
          break;
        case "option":
          Kt(e, a);
          break;
        case "select":
          ks(e, a), Mn("invalid", e);
          break;
        case "textarea":
          oh(e, a), Mn("invalid", e);
          break;
      }
      qc(t, a);
      {
        E = /* @__PURE__ */ new Set();
        for (var w = e.attributes, V = 0; V < w.length; V++) {
          var $ = w[V].name.toLowerCase();
          switch ($) {
            case "value":
              break;
            case "checked":
              break;
            case "selected":
              break;
            default:
              E.add(w[V].name);
          }
        }
      }
      var X = null;
      for (var Z in a)
        if (a.hasOwnProperty(Z)) {
          var ne = a[Z];
          if (Z === Ec)
            typeof ne == "string" ? e.textContent !== ne && (a[ts] !== !0 && Om(e.textContent, ne, c, p), X = [Ec, ne]) : typeof ne == "number" && e.textContent !== "" + ne && (a[ts] !== !0 && Om(e.textContent, ne, c, p), X = [Ec, "" + ne]);
          else if (we.hasOwnProperty(Z))
            ne != null && (typeof ne != "function" && _m(Z, ne), Z === "onScroll" && Mn("scroll", e));
          else if (p && // Convince Flow we've calculated it (it's DEV-only in this method.)
          typeof m == "boolean") {
            var Me = void 0, lt = gn(Z);
            if (a[ts] !== !0) {
              if (!(Z === Rm || Z === ts || // Controlled attributes are not validated
              // TODO: Only ignore them on controlled tags.
              Z === "value" || Z === "checked" || Z === "selected")) {
                if (Z === Qp) {
                  var tt = e.innerHTML, jt = ne ? ne[wm] : void 0;
                  if (jt != null) {
                    var Lt = WC(e, jt);
                    Lt !== tt && qp(Z, tt, Lt);
                  }
                } else if (Z === Cc) {
                  if (E.delete(Z), YC) {
                    var W = Ag(ne);
                    Me = e.getAttribute("style"), W !== Me && qp(Z, Me, W);
                  }
                } else if (m)
                  E.delete(Z.toLowerCase()), Me = Di(e, Z, ne), ne !== Me && qp(Z, Me, ne);
                else if (!Tn(Z, lt, m) && !vr(Z, ne, lt, m)) {
                  var re = !1;
                  if (lt !== null)
                    E.delete(lt.attributeName), Me = Cl(e, Z, ne, lt);
                  else {
                    var G = i;
                    if (G === mi && (G = Wd(t)), G === mi)
                      E.delete(Z.toLowerCase());
                    else {
                      var me = px(Z);
                      me !== null && me !== Z && (re = !0, E.delete(me)), E.delete(Z);
                    }
                    Me = Di(e, Z, ne);
                  }
                  var We = I;
                  !We && ne !== Me && !re && qp(Z, Me, ne);
                }
              }
            }
          }
        }
      switch (p && // $FlowFixMe - Should be inferred as not undefined.
      E.size > 0 && a[ts] !== !0 && IC(E), t) {
        case "input":
          Qa(e), K(e, a, !0);
          break;
        case "textarea":
          Qa(e), uh(e);
          break;
        case "select":
        case "option":
          break;
        default:
          typeof a.onClick == "function" && Dm(e);
          break;
      }
      return X;
    }
    function hx(e, t, a) {
      var i = e.nodeValue !== t;
      return i;
    }
    function o0(e, t) {
      {
        if (ai)
          return;
        ai = !0, g("Did not expect server HTML to contain a <%s> in <%s>.", t.nodeName.toLowerCase(), e.nodeName.toLowerCase());
      }
    }
    function l0(e, t) {
      {
        if (ai)
          return;
        ai = !0, g('Did not expect server HTML to contain the text node "%s" in <%s>.', t.nodeValue, e.nodeName.toLowerCase());
      }
    }
    function u0(e, t, a) {
      {
        if (ai)
          return;
        ai = !0, g("Expected server HTML to contain a matching <%s> in <%s>.", t, e.nodeName.toLowerCase());
      }
    }
    function s0(e, t) {
      {
        if (t === "" || ai)
          return;
        ai = !0, g('Expected server HTML to contain a matching text node for "%s" in <%s>.', t, e.nodeName.toLowerCase());
      }
    }
    function mx(e, t, a) {
      switch (t) {
        case "input":
          ee(e, a);
          return;
        case "textarea":
          wg(e, a);
          return;
        case "select":
          Id(e, a);
          return;
      }
    }
    var Kp = function() {
    }, Xp = function() {
    };
    {
      var yx = ["address", "applet", "area", "article", "aside", "base", "basefont", "bgsound", "blockquote", "body", "br", "button", "caption", "center", "col", "colgroup", "dd", "details", "dir", "div", "dl", "dt", "embed", "fieldset", "figcaption", "figure", "footer", "form", "frame", "frameset", "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hgroup", "hr", "html", "iframe", "img", "input", "isindex", "li", "link", "listing", "main", "marquee", "menu", "menuitem", "meta", "nav", "noembed", "noframes", "noscript", "object", "ol", "p", "param", "plaintext", "pre", "script", "section", "select", "source", "style", "summary", "table", "tbody", "td", "template", "textarea", "tfoot", "th", "thead", "title", "tr", "track", "ul", "wbr", "xmp"], QC = [
        "applet",
        "caption",
        "html",
        "table",
        "td",
        "th",
        "marquee",
        "object",
        "template",
        // https://html.spec.whatwg.org/multipage/syntax.html#html-integration-point
        // TODO: Distinguish by namespace here -- for <title>, including it here
        // errs on the side of fewer warnings
        "foreignObject",
        "desc",
        "title"
      ], gx = QC.concat(["button"]), Sx = ["dd", "dt", "li", "option", "optgroup", "p", "rp", "rt"], qC = {
        current: null,
        formTag: null,
        aTagInScope: null,
        buttonTagInScope: null,
        nobrTagInScope: null,
        pTagInButtonScope: null,
        listItemTagAutoclosing: null,
        dlItemTagAutoclosing: null
      };
      Xp = function(e, t) {
        var a = Et({}, e || qC), i = {
          tag: t
        };
        return QC.indexOf(t) !== -1 && (a.aTagInScope = null, a.buttonTagInScope = null, a.nobrTagInScope = null), gx.indexOf(t) !== -1 && (a.pTagInButtonScope = null), yx.indexOf(t) !== -1 && t !== "address" && t !== "div" && t !== "p" && (a.listItemTagAutoclosing = null, a.dlItemTagAutoclosing = null), a.current = i, t === "form" && (a.formTag = i), t === "a" && (a.aTagInScope = i), t === "button" && (a.buttonTagInScope = i), t === "nobr" && (a.nobrTagInScope = i), t === "p" && (a.pTagInButtonScope = i), t === "li" && (a.listItemTagAutoclosing = i), (t === "dd" || t === "dt") && (a.dlItemTagAutoclosing = i), a;
      };
      var Ex = function(e, t) {
        switch (t) {
          case "select":
            return e === "option" || e === "optgroup" || e === "#text";
          case "optgroup":
            return e === "option" || e === "#text";
          case "option":
            return e === "#text";
          case "tr":
            return e === "th" || e === "td" || e === "style" || e === "script" || e === "template";
          case "tbody":
          case "thead":
          case "tfoot":
            return e === "tr" || e === "style" || e === "script" || e === "template";
          case "colgroup":
            return e === "col" || e === "template";
          case "table":
            return e === "caption" || e === "colgroup" || e === "tbody" || e === "tfoot" || e === "thead" || e === "style" || e === "script" || e === "template";
          case "head":
            return e === "base" || e === "basefont" || e === "bgsound" || e === "link" || e === "meta" || e === "title" || e === "noscript" || e === "noframes" || e === "style" || e === "script" || e === "template";
          case "html":
            return e === "head" || e === "body" || e === "frameset";
          case "frameset":
            return e === "frame";
          case "#document":
            return e === "html";
        }
        switch (e) {
          case "h1":
          case "h2":
          case "h3":
          case "h4":
          case "h5":
          case "h6":
            return t !== "h1" && t !== "h2" && t !== "h3" && t !== "h4" && t !== "h5" && t !== "h6";
          case "rp":
          case "rt":
            return Sx.indexOf(t) === -1;
          case "body":
          case "caption":
          case "col":
          case "colgroup":
          case "frameset":
          case "frame":
          case "head":
          case "html":
          case "tbody":
          case "td":
          case "tfoot":
          case "th":
          case "thead":
          case "tr":
            return t == null;
        }
        return !0;
      }, Cx = function(e, t) {
        switch (e) {
          case "address":
          case "article":
          case "aside":
          case "blockquote":
          case "center":
          case "details":
          case "dialog":
          case "dir":
          case "div":
          case "dl":
          case "fieldset":
          case "figcaption":
          case "figure":
          case "footer":
          case "header":
          case "hgroup":
          case "main":
          case "menu":
          case "nav":
          case "ol":
          case "p":
          case "section":
          case "summary":
          case "ul":
          case "pre":
          case "listing":
          case "table":
          case "hr":
          case "xmp":
          case "h1":
          case "h2":
          case "h3":
          case "h4":
          case "h5":
          case "h6":
            return t.pTagInButtonScope;
          case "form":
            return t.formTag || t.pTagInButtonScope;
          case "li":
            return t.listItemTagAutoclosing;
          case "dd":
          case "dt":
            return t.dlItemTagAutoclosing;
          case "button":
            return t.buttonTagInScope;
          case "a":
            return t.aTagInScope;
          case "nobr":
            return t.nobrTagInScope;
        }
        return null;
      }, KC = {};
      Kp = function(e, t, a) {
        a = a || qC;
        var i = a.current, l = i && i.tag;
        t != null && (e != null && g("validateDOMNesting: when childText is passed, childTag should be null"), e = "#text");
        var c = Ex(e, l) ? null : i, p = c ? null : Cx(e, a), m = c || p;
        if (m) {
          var E = m.tag, R = !!c + "|" + e + "|" + E;
          if (!KC[R]) {
            KC[R] = !0;
            var w = e, V = "";
            if (e === "#text" ? /\S/.test(t) ? w = "Text nodes" : (w = "Whitespace text nodes", V = " Make sure you don't have any extra whitespace between tags on each line of your source code.") : w = "<" + e + ">", c) {
              var $ = "";
              E === "table" && e === "tr" && ($ += " Add a <tbody>, <thead> or <tfoot> to your code to match the DOM tree generated by the browser."), g("validateDOMNesting(...): %s cannot appear as a child of <%s>.%s%s", w, E, V, $);
            } else
              g("validateDOMNesting(...): %s cannot appear as a descendant of <%s>.", w, E);
          }
        }
      };
    }
    var Nm = "suppressHydrationWarning", Am = "$", Mm = "/$", Jp = "$?", Zp = "$!", bx = "style", c0 = null, f0 = null;
    function Tx(e) {
      var t, a, i = e.nodeType;
      switch (i) {
        case po:
        case Os: {
          t = i === po ? "#document" : "#fragment";
          var l = e.documentElement;
          a = l ? l.namespaceURI : Wc(null, "");
          break;
        }
        default: {
          var c = i === qn ? e.parentNode : e, p = c.namespaceURI || null;
          t = c.tagName, a = Wc(p, t);
          break;
        }
      }
      {
        var m = t.toLowerCase(), E = Xp(null, m);
        return {
          namespace: a,
          ancestorInfo: E
        };
      }
    }
    function Rx(e, t, a) {
      {
        var i = e, l = Wc(i.namespace, t), c = Xp(i.ancestorInfo, t);
        return {
          namespace: l,
          ancestorInfo: c
        };
      }
    }
    function Lz(e) {
      return e;
    }
    function wx(e) {
      c0 = kr(), f0 = Fw();
      var t = null;
      return In(!1), t;
    }
    function xx(e) {
      jw(f0), In(c0), c0 = null, f0 = null;
    }
    function _x(e, t, a, i, l) {
      var c;
      {
        var p = i;
        if (Kp(e, null, p.ancestorInfo), typeof t.children == "string" || typeof t.children == "number") {
          var m = "" + t.children, E = Xp(p.ancestorInfo, e);
          Kp(null, m, E);
        }
        c = p.namespace;
      }
      var R = ux(e, t, a, c);
      return nv(l, R), S0(R, t), R;
    }
    function kx(e, t) {
      e.appendChild(t);
    }
    function Ox(e, t, a, i, l) {
      switch (cx(e, t, a, i), t) {
        case "button":
        case "input":
        case "select":
        case "textarea":
          return !!a.autoFocus;
        case "img":
          return !0;
        default:
          return !1;
      }
    }
    function Dx(e, t, a, i, l, c) {
      {
        var p = c;
        if (typeof i.children != typeof a.children && (typeof i.children == "string" || typeof i.children == "number")) {
          var m = "" + i.children, E = Xp(p.ancestorInfo, t);
          Kp(null, m, E);
        }
      }
      return fx(e, t, a, i);
    }
    function d0(e, t) {
      return e === "textarea" || e === "noscript" || typeof t.children == "string" || typeof t.children == "number" || typeof t.dangerouslySetInnerHTML == "object" && t.dangerouslySetInnerHTML !== null && t.dangerouslySetInnerHTML.__html != null;
    }
    function Nx(e, t, a, i) {
      {
        var l = a;
        Kp(null, e, l.ancestorInfo);
      }
      var c = sx(e, t);
      return nv(i, c), c;
    }
    function Ax() {
      var e = window.event;
      return e === void 0 ? xr : Qu(e.type);
    }
    var p0 = typeof setTimeout == "function" ? setTimeout : void 0, Mx = typeof clearTimeout == "function" ? clearTimeout : void 0, v0 = -1, XC = typeof Promise == "function" ? Promise : void 0, Lx = typeof queueMicrotask == "function" ? queueMicrotask : typeof XC < "u" ? function(e) {
      return XC.resolve(null).then(e).catch(zx);
    } : p0;
    function zx(e) {
      setTimeout(function() {
        throw e;
      });
    }
    function Ux(e, t, a, i) {
      switch (t) {
        case "button":
        case "input":
        case "select":
        case "textarea":
          a.autoFocus && e.focus();
          return;
        case "img": {
          a.src && (e.src = a.src);
          return;
        }
      }
    }
    function Px(e, t, a, i, l, c) {
      dx(e, t, a, i, l), S0(e, l);
    }
    function JC(e) {
      Po(e, "");
    }
    function $x(e, t, a) {
      e.nodeValue = a;
    }
    function Fx(e, t) {
      e.appendChild(t);
    }
    function jx(e, t) {
      var a;
      e.nodeType === qn ? (a = e.parentNode, a.insertBefore(t, e)) : (a = e, a.appendChild(t));
      var i = e._reactRootContainer;
      i == null && a.onclick === null && Dm(a);
    }
    function Hx(e, t, a) {
      e.insertBefore(t, a);
    }
    function Vx(e, t, a) {
      e.nodeType === qn ? e.parentNode.insertBefore(t, a) : e.insertBefore(t, a);
    }
    function Bx(e, t) {
      e.removeChild(t);
    }
    function Ix(e, t) {
      e.nodeType === qn ? e.parentNode.removeChild(t) : e.removeChild(t);
    }
    function h0(e, t) {
      var a = t, i = 0;
      do {
        var l = a.nextSibling;
        if (e.removeChild(a), l && l.nodeType === qn) {
          var c = l.data;
          if (c === Mm)
            if (i === 0) {
              e.removeChild(l), Br(t);
              return;
            } else
              i--;
          else (c === Am || c === Jp || c === Zp) && i++;
        }
        a = l;
      } while (a);
      Br(t);
    }
    function Yx(e, t) {
      e.nodeType === qn ? h0(e.parentNode, t) : e.nodeType === da && h0(e, t), Br(e);
    }
    function Wx(e) {
      e = e;
      var t = e.style;
      typeof t.setProperty == "function" ? t.setProperty("display", "none", "important") : t.display = "none";
    }
    function Gx(e) {
      e.nodeValue = "";
    }
    function Qx(e, t) {
      e = e;
      var a = t[bx], i = a != null && a.hasOwnProperty("display") ? a.display : null;
      e.style.display = Qc("display", i);
    }
    function qx(e, t) {
      e.nodeValue = t;
    }
    function Kx(e) {
      e.nodeType === da ? e.textContent = "" : e.nodeType === po && e.documentElement && e.removeChild(e.documentElement);
    }
    function Xx(e, t, a) {
      return e.nodeType !== da || t.toLowerCase() !== e.nodeName.toLowerCase() ? null : e;
    }
    function Jx(e, t) {
      return t === "" || e.nodeType !== fo ? null : e;
    }
    function Zx(e) {
      return e.nodeType !== qn ? null : e;
    }
    function ZC(e) {
      return e.data === Jp;
    }
    function m0(e) {
      return e.data === Zp;
    }
    function e_(e) {
      var t = e.nextSibling && e.nextSibling.dataset, a, i, l;
      return t && (a = t.dgst, i = t.msg, l = t.stck), {
        message: i,
        digest: a,
        stack: l
      };
    }
    function t_(e, t) {
      e._reactRetry = t;
    }
    function Lm(e) {
      for (; e != null; e = e.nextSibling) {
        var t = e.nodeType;
        if (t === da || t === fo)
          break;
        if (t === qn) {
          var a = e.data;
          if (a === Am || a === Zp || a === Jp)
            break;
          if (a === Mm)
            return null;
        }
      }
      return e;
    }
    function ev(e) {
      return Lm(e.nextSibling);
    }
    function n_(e) {
      return Lm(e.firstChild);
    }
    function r_(e) {
      return Lm(e.firstChild);
    }
    function a_(e) {
      return Lm(e.nextSibling);
    }
    function i_(e, t, a, i, l, c, p) {
      nv(c, e), S0(e, a);
      var m;
      {
        var E = l;
        m = E.namespace;
      }
      var R = (c.mode & Dt) !== rt;
      return vx(e, t, a, m, i, R, p);
    }
    function o_(e, t, a, i) {
      return nv(a, e), a.mode & Dt, hx(e, t);
    }
    function l_(e, t) {
      nv(t, e);
    }
    function u_(e) {
      for (var t = e.nextSibling, a = 0; t; ) {
        if (t.nodeType === qn) {
          var i = t.data;
          if (i === Mm) {
            if (a === 0)
              return ev(t);
            a--;
          } else (i === Am || i === Zp || i === Jp) && a++;
        }
        t = t.nextSibling;
      }
      return null;
    }
    function eb(e) {
      for (var t = e.previousSibling, a = 0; t; ) {
        if (t.nodeType === qn) {
          var i = t.data;
          if (i === Am || i === Zp || i === Jp) {
            if (a === 0)
              return t;
            a--;
          } else i === Mm && a++;
        }
        t = t.previousSibling;
      }
      return null;
    }
    function s_(e) {
      Br(e);
    }
    function c_(e) {
      Br(e);
    }
    function f_(e) {
      return e !== "head" && e !== "body";
    }
    function d_(e, t, a, i) {
      var l = !0;
      Om(t.nodeValue, a, i, l);
    }
    function p_(e, t, a, i, l, c) {
      if (t[Nm] !== !0) {
        var p = !0;
        Om(i.nodeValue, l, c, p);
      }
    }
    function v_(e, t) {
      t.nodeType === da ? o0(e, t) : t.nodeType === qn || l0(e, t);
    }
    function h_(e, t) {
      {
        var a = e.parentNode;
        a !== null && (t.nodeType === da ? o0(a, t) : t.nodeType === qn || l0(a, t));
      }
    }
    function m_(e, t, a, i, l) {
      (l || t[Nm] !== !0) && (i.nodeType === da ? o0(a, i) : i.nodeType === qn || l0(a, i));
    }
    function y_(e, t, a) {
      u0(e, t);
    }
    function g_(e, t) {
      s0(e, t);
    }
    function S_(e, t, a) {
      {
        var i = e.parentNode;
        i !== null && u0(i, t);
      }
    }
    function E_(e, t) {
      {
        var a = e.parentNode;
        a !== null && s0(a, t);
      }
    }
    function C_(e, t, a, i, l, c) {
      (c || t[Nm] !== !0) && u0(a, i);
    }
    function b_(e, t, a, i, l) {
      (l || t[Nm] !== !0) && s0(a, i);
    }
    function T_(e) {
      g("An error occurred during hydration. The server HTML was replaced with client content in <%s>.", e.nodeName.toLowerCase());
    }
    function R_(e) {
      Wp(e);
    }
    var rd = Math.random().toString(36).slice(2), ad = "__reactFiber$" + rd, y0 = "__reactProps$" + rd, tv = "__reactContainer$" + rd, g0 = "__reactEvents$" + rd, w_ = "__reactListeners$" + rd, x_ = "__reactHandles$" + rd;
    function __(e) {
      delete e[ad], delete e[y0], delete e[g0], delete e[w_], delete e[x_];
    }
    function nv(e, t) {
      t[ad] = e;
    }
    function zm(e, t) {
      t[tv] = e;
    }
    function tb(e) {
      e[tv] = null;
    }
    function rv(e) {
      return !!e[tv];
    }
    function bc(e) {
      var t = e[ad];
      if (t)
        return t;
      for (var a = e.parentNode; a; ) {
        if (t = a[tv] || a[ad], t) {
          var i = t.alternate;
          if (t.child !== null || i !== null && i.child !== null)
            for (var l = eb(e); l !== null; ) {
              var c = l[ad];
              if (c)
                return c;
              l = eb(l);
            }
          return t;
        }
        e = a, a = e.parentNode;
      }
      return null;
    }
    function ns(e) {
      var t = e[ad] || e[tv];
      return t && (t.tag === B || t.tag === M || t.tag === se || t.tag === U) ? t : null;
    }
    function id(e) {
      if (e.tag === B || e.tag === M)
        return e.stateNode;
      throw new Error("getNodeFromInstance: Invalid argument.");
    }
    function Um(e) {
      return e[y0] || null;
    }
    function S0(e, t) {
      e[y0] = t;
    }
    function k_(e) {
      var t = e[g0];
      return t === void 0 && (t = e[g0] = /* @__PURE__ */ new Set()), t;
    }
    var nb = {}, rb = y.ReactDebugCurrentFrame;
    function Pm(e) {
      if (e) {
        var t = e._owner, a = Ts(e.type, e._source, t ? t.type : null);
        rb.setExtraStackFrame(a);
      } else
        rb.setExtraStackFrame(null);
    }
    function Eo(e, t, a, i, l) {
      {
        var c = Function.call.bind(Te);
        for (var p in e)
          if (c(e, p)) {
            var m = void 0;
            try {
              if (typeof e[p] != "function") {
                var E = Error((i || "React class") + ": " + a + " type `" + p + "` is invalid; it must be a function, usually from the `prop-types` package, but received `" + typeof e[p] + "`.This often happens because of typos such as `PropTypes.function` instead of `PropTypes.func`.");
                throw E.name = "Invariant Violation", E;
              }
              m = e[p](t, p, i, a, null, "SECRET_DO_NOT_PASS_THIS_OR_YOU_WILL_BE_FIRED");
            } catch (R) {
              m = R;
            }
            m && !(m instanceof Error) && (Pm(l), g("%s: type specification of %s `%s` is invalid; the type checker function must return `null` or an `Error` but returned a %s. You may have forgotten to pass an argument to the type checker creator (arrayOf, instanceOf, objectOf, oneOf, oneOfType, and shape all require an argument).", i || "React class", a, p, typeof m), Pm(null)), m instanceof Error && !(m.message in nb) && (nb[m.message] = !0, Pm(l), g("Failed %s type: %s", a, m.message), Pm(null));
          }
      }
    }
    var E0 = [], $m;
    $m = [];
    var eu = -1;
    function rs(e) {
      return {
        current: e
      };
    }
    function Ca(e, t) {
      if (eu < 0) {
        g("Unexpected pop.");
        return;
      }
      t !== $m[eu] && g("Unexpected Fiber popped."), e.current = E0[eu], E0[eu] = null, $m[eu] = null, eu--;
    }
    function ba(e, t, a) {
      eu++, E0[eu] = e.current, $m[eu] = a, e.current = t;
    }
    var C0;
    C0 = {};
    var Ri = {};
    Object.freeze(Ri);
    var tu = rs(Ri), il = rs(!1), b0 = Ri;
    function od(e, t, a) {
      return a && ol(t) ? b0 : tu.current;
    }
    function ab(e, t, a) {
      {
        var i = e.stateNode;
        i.__reactInternalMemoizedUnmaskedChildContext = t, i.__reactInternalMemoizedMaskedChildContext = a;
      }
    }
    function ld(e, t) {
      {
        var a = e.type, i = a.contextTypes;
        if (!i)
          return Ri;
        var l = e.stateNode;
        if (l && l.__reactInternalMemoizedUnmaskedChildContext === t)
          return l.__reactInternalMemoizedMaskedChildContext;
        var c = {};
        for (var p in i)
          c[p] = t[p];
        {
          var m = ht(e) || "Unknown";
          Eo(i, c, "context", m);
        }
        return l && ab(e, t, c), c;
      }
    }
    function Fm() {
      return il.current;
    }
    function ol(e) {
      {
        var t = e.childContextTypes;
        return t != null;
      }
    }
    function jm(e) {
      Ca(il, e), Ca(tu, e);
    }
    function T0(e) {
      Ca(il, e), Ca(tu, e);
    }
    function ib(e, t, a) {
      {
        if (tu.current !== Ri)
          throw new Error("Unexpected context found on stack. This error is likely caused by a bug in React. Please file an issue.");
        ba(tu, t, e), ba(il, a, e);
      }
    }
    function ob(e, t, a) {
      {
        var i = e.stateNode, l = t.childContextTypes;
        if (typeof i.getChildContext != "function") {
          {
            var c = ht(e) || "Unknown";
            C0[c] || (C0[c] = !0, g("%s.childContextTypes is specified but there is no getChildContext() method on the instance. You can either define getChildContext() on %s or remove childContextTypes from it.", c, c));
          }
          return a;
        }
        var p = i.getChildContext();
        for (var m in p)
          if (!(m in l))
            throw new Error((ht(e) || "Unknown") + '.getChildContext(): key "' + m + '" is not defined in childContextTypes.');
        {
          var E = ht(e) || "Unknown";
          Eo(l, p, "child context", E);
        }
        return Et({}, a, p);
      }
    }
    function Hm(e) {
      {
        var t = e.stateNode, a = t && t.__reactInternalMemoizedMergedChildContext || Ri;
        return b0 = tu.current, ba(tu, a, e), ba(il, il.current, e), !0;
      }
    }
    function lb(e, t, a) {
      {
        var i = e.stateNode;
        if (!i)
          throw new Error("Expected to have an instance by this point. This error is likely caused by a bug in React. Please file an issue.");
        if (a) {
          var l = ob(e, t, b0);
          i.__reactInternalMemoizedMergedChildContext = l, Ca(il, e), Ca(tu, e), ba(tu, l, e), ba(il, a, e);
        } else
          Ca(il, e), ba(il, a, e);
      }
    }
    function O_(e) {
      {
        if (!Uh(e) || e.tag !== A)
          throw new Error("Expected subtree parent to be a mounted class component. This error is likely caused by a bug in React. Please file an issue.");
        var t = e;
        do {
          switch (t.tag) {
            case U:
              return t.stateNode.context;
            case A: {
              var a = t.type;
              if (ol(a))
                return t.stateNode.__reactInternalMemoizedMergedChildContext;
              break;
            }
          }
          t = t.return;
        } while (t !== null);
        throw new Error("Found unexpected detached subtree parent. This error is likely caused by a bug in React. Please file an issue.");
      }
    }
    var as = 0, Vm = 1, nu = null, R0 = !1, w0 = !1;
    function ub(e) {
      nu === null ? nu = [e] : nu.push(e);
    }
    function D_(e) {
      R0 = !0, ub(e);
    }
    function sb() {
      R0 && is();
    }
    function is() {
      if (!w0 && nu !== null) {
        w0 = !0;
        var e = 0, t = za();
        try {
          var a = !0, i = nu;
          for (lr(Sa); e < i.length; e++) {
            var l = i[e];
            do
              l = l(a);
            while (l !== null);
          }
          nu = null, R0 = !1;
        } catch (c) {
          throw nu !== null && (nu = nu.slice(e + 1)), lp(mo, is), c;
        } finally {
          lr(t), w0 = !1;
        }
      }
      return null;
    }
    var ud = [], sd = 0, Bm = null, Im = 0, Yi = [], Wi = 0, Tc = null, ru = 1, au = "";
    function N_(e) {
      return wc(), (e.flags & Bs) !== nt;
    }
    function A_(e) {
      return wc(), Im;
    }
    function M_() {
      var e = au, t = ru, a = t & ~L_(t);
      return a.toString(32) + e;
    }
    function Rc(e, t) {
      wc(), ud[sd++] = Im, ud[sd++] = Bm, Bm = e, Im = t;
    }
    function cb(e, t, a) {
      wc(), Yi[Wi++] = ru, Yi[Wi++] = au, Yi[Wi++] = Tc, Tc = e;
      var i = ru, l = au, c = Ym(i) - 1, p = i & ~(1 << c), m = a + 1, E = Ym(t) + c;
      if (E > 30) {
        var R = c - c % 5, w = (1 << R) - 1, V = (p & w).toString(32), $ = p >> R, X = c - R, Z = Ym(t) + X, ne = m << X, Me = ne | $, lt = V + l;
        ru = 1 << Z | Me, au = lt;
      } else {
        var tt = m << c, jt = tt | p, Lt = l;
        ru = 1 << E | jt, au = Lt;
      }
    }
    function x0(e) {
      wc();
      var t = e.return;
      if (t !== null) {
        var a = 1, i = 0;
        Rc(e, a), cb(e, a, i);
      }
    }
    function Ym(e) {
      return 32 - or(e);
    }
    function L_(e) {
      return 1 << Ym(e) - 1;
    }
    function _0(e) {
      for (; e === Bm; )
        Bm = ud[--sd], ud[sd] = null, Im = ud[--sd], ud[sd] = null;
      for (; e === Tc; )
        Tc = Yi[--Wi], Yi[Wi] = null, au = Yi[--Wi], Yi[Wi] = null, ru = Yi[--Wi], Yi[Wi] = null;
    }
    function z_() {
      return wc(), Tc !== null ? {
        id: ru,
        overflow: au
      } : null;
    }
    function U_(e, t) {
      wc(), Yi[Wi++] = ru, Yi[Wi++] = au, Yi[Wi++] = Tc, ru = t.id, au = t.overflow, Tc = e;
    }
    function wc() {
      Jr() || g("Expected to be hydrating. This is a bug in React. Please file an issue.");
    }
    var Xr = null, Gi = null, Co = !1, xc = !1, os = null;
    function P_() {
      Co && g("We should not be hydrating here. This is a bug in React. Please file a bug.");
    }
    function fb() {
      xc = !0;
    }
    function $_() {
      return xc;
    }
    function F_(e) {
      var t = e.stateNode.containerInfo;
      return Gi = r_(t), Xr = e, Co = !0, os = null, xc = !1, !0;
    }
    function j_(e, t, a) {
      return Gi = a_(t), Xr = e, Co = !0, os = null, xc = !1, a !== null && U_(e, a), !0;
    }
    function db(e, t) {
      switch (e.tag) {
        case U: {
          v_(e.stateNode.containerInfo, t);
          break;
        }
        case B: {
          var a = (e.mode & Dt) !== rt;
          m_(
            e.type,
            e.memoizedProps,
            e.stateNode,
            t,
            // TODO: Delete this argument when we remove the legacy root API.
            a
          );
          break;
        }
        case se: {
          var i = e.memoizedState;
          i.dehydrated !== null && h_(i.dehydrated, t);
          break;
        }
      }
    }
    function pb(e, t) {
      db(e, t);
      var a = ID();
      a.stateNode = t, a.return = e;
      var i = e.deletions;
      i === null ? (e.deletions = [a], e.flags |= pa) : i.push(a);
    }
    function k0(e, t) {
      {
        if (xc)
          return;
        switch (e.tag) {
          case U: {
            var a = e.stateNode.containerInfo;
            switch (t.tag) {
              case B:
                var i = t.type;
                t.pendingProps, y_(a, i);
                break;
              case M:
                var l = t.pendingProps;
                g_(a, l);
                break;
            }
            break;
          }
          case B: {
            var c = e.type, p = e.memoizedProps, m = e.stateNode;
            switch (t.tag) {
              case B: {
                var E = t.type, R = t.pendingProps, w = (e.mode & Dt) !== rt;
                C_(
                  c,
                  p,
                  m,
                  E,
                  R,
                  // TODO: Delete this argument when we remove the legacy root API.
                  w
                );
                break;
              }
              case M: {
                var V = t.pendingProps, $ = (e.mode & Dt) !== rt;
                b_(
                  c,
                  p,
                  m,
                  V,
                  // TODO: Delete this argument when we remove the legacy root API.
                  $
                );
                break;
              }
            }
            break;
          }
          case se: {
            var X = e.memoizedState, Z = X.dehydrated;
            if (Z !== null) switch (t.tag) {
              case B:
                var ne = t.type;
                t.pendingProps, S_(Z, ne);
                break;
              case M:
                var Me = t.pendingProps;
                E_(Z, Me);
                break;
            }
            break;
          }
          default:
            return;
        }
      }
    }
    function vb(e, t) {
      t.flags = t.flags & -4097 | Kn, k0(e, t);
    }
    function hb(e, t) {
      switch (e.tag) {
        case B: {
          var a = e.type;
          e.pendingProps;
          var i = Xx(t, a);
          return i !== null ? (e.stateNode = i, Xr = e, Gi = n_(i), !0) : !1;
        }
        case M: {
          var l = e.pendingProps, c = Jx(t, l);
          return c !== null ? (e.stateNode = c, Xr = e, Gi = null, !0) : !1;
        }
        case se: {
          var p = Zx(t);
          if (p !== null) {
            var m = {
              dehydrated: p,
              treeContext: z_(),
              retryLane: La
            };
            e.memoizedState = m;
            var E = YD(p);
            return E.return = e, e.child = E, Xr = e, Gi = null, !0;
          }
          return !1;
        }
        default:
          return !1;
      }
    }
    function O0(e) {
      return (e.mode & Dt) !== rt && (e.flags & Ot) === nt;
    }
    function D0(e) {
      throw new Error("Hydration failed because the initial UI does not match what was rendered on the server.");
    }
    function N0(e) {
      if (Co) {
        var t = Gi;
        if (!t) {
          O0(e) && (k0(Xr, e), D0()), vb(Xr, e), Co = !1, Xr = e;
          return;
        }
        var a = t;
        if (!hb(e, t)) {
          O0(e) && (k0(Xr, e), D0()), t = ev(a);
          var i = Xr;
          if (!t || !hb(e, t)) {
            vb(Xr, e), Co = !1, Xr = e;
            return;
          }
          pb(i, a);
        }
      }
    }
    function H_(e, t, a) {
      var i = e.stateNode, l = !xc, c = i_(i, e.type, e.memoizedProps, t, a, e, l);
      return e.updateQueue = c, c !== null;
    }
    function V_(e) {
      var t = e.stateNode, a = e.memoizedProps, i = o_(t, a, e);
      if (i) {
        var l = Xr;
        if (l !== null)
          switch (l.tag) {
            case U: {
              var c = l.stateNode.containerInfo, p = (l.mode & Dt) !== rt;
              d_(
                c,
                t,
                a,
                // TODO: Delete this argument when we remove the legacy root API.
                p
              );
              break;
            }
            case B: {
              var m = l.type, E = l.memoizedProps, R = l.stateNode, w = (l.mode & Dt) !== rt;
              p_(
                m,
                E,
                R,
                t,
                a,
                // TODO: Delete this argument when we remove the legacy root API.
                w
              );
              break;
            }
          }
      }
      return i;
    }
    function B_(e) {
      var t = e.memoizedState, a = t !== null ? t.dehydrated : null;
      if (!a)
        throw new Error("Expected to have a hydrated suspense instance. This error is likely caused by a bug in React. Please file an issue.");
      l_(a, e);
    }
    function I_(e) {
      var t = e.memoizedState, a = t !== null ? t.dehydrated : null;
      if (!a)
        throw new Error("Expected to have a hydrated suspense instance. This error is likely caused by a bug in React. Please file an issue.");
      return u_(a);
    }
    function mb(e) {
      for (var t = e.return; t !== null && t.tag !== B && t.tag !== U && t.tag !== se; )
        t = t.return;
      Xr = t;
    }
    function Wm(e) {
      if (e !== Xr)
        return !1;
      if (!Co)
        return mb(e), Co = !0, !1;
      if (e.tag !== U && (e.tag !== B || f_(e.type) && !d0(e.type, e.memoizedProps))) {
        var t = Gi;
        if (t)
          if (O0(e))
            yb(e), D0();
          else
            for (; t; )
              pb(e, t), t = ev(t);
      }
      return mb(e), e.tag === se ? Gi = I_(e) : Gi = Xr ? ev(e.stateNode) : null, !0;
    }
    function Y_() {
      return Co && Gi !== null;
    }
    function yb(e) {
      for (var t = Gi; t; )
        db(e, t), t = ev(t);
    }
    function cd() {
      Xr = null, Gi = null, Co = !1, xc = !1;
    }
    function gb() {
      os !== null && (fT(os), os = null);
    }
    function Jr() {
      return Co;
    }
    function A0(e) {
      os === null ? os = [e] : os.push(e);
    }
    var W_ = y.ReactCurrentBatchConfig, G_ = null;
    function Q_() {
      return W_.transition;
    }
    var bo = {
      recordUnsafeLifecycleWarnings: function(e, t) {
      },
      flushPendingUnsafeLifecycleWarnings: function() {
      },
      recordLegacyContextWarning: function(e, t) {
      },
      flushLegacyContextWarning: function() {
      },
      discardPendingWarnings: function() {
      }
    };
    {
      var q_ = function(e) {
        for (var t = null, a = e; a !== null; )
          a.mode & Ct && (t = a), a = a.return;
        return t;
      }, _c = function(e) {
        var t = [];
        return e.forEach(function(a) {
          t.push(a);
        }), t.sort().join(", ");
      }, av = [], iv = [], ov = [], lv = [], uv = [], sv = [], kc = /* @__PURE__ */ new Set();
      bo.recordUnsafeLifecycleWarnings = function(e, t) {
        kc.has(e.type) || (typeof t.componentWillMount == "function" && // Don't warn about react-lifecycles-compat polyfilled components.
        t.componentWillMount.__suppressDeprecationWarning !== !0 && av.push(e), e.mode & Ct && typeof t.UNSAFE_componentWillMount == "function" && iv.push(e), typeof t.componentWillReceiveProps == "function" && t.componentWillReceiveProps.__suppressDeprecationWarning !== !0 && ov.push(e), e.mode & Ct && typeof t.UNSAFE_componentWillReceiveProps == "function" && lv.push(e), typeof t.componentWillUpdate == "function" && t.componentWillUpdate.__suppressDeprecationWarning !== !0 && uv.push(e), e.mode & Ct && typeof t.UNSAFE_componentWillUpdate == "function" && sv.push(e));
      }, bo.flushPendingUnsafeLifecycleWarnings = function() {
        var e = /* @__PURE__ */ new Set();
        av.length > 0 && (av.forEach(function($) {
          e.add(ht($) || "Component"), kc.add($.type);
        }), av = []);
        var t = /* @__PURE__ */ new Set();
        iv.length > 0 && (iv.forEach(function($) {
          t.add(ht($) || "Component"), kc.add($.type);
        }), iv = []);
        var a = /* @__PURE__ */ new Set();
        ov.length > 0 && (ov.forEach(function($) {
          a.add(ht($) || "Component"), kc.add($.type);
        }), ov = []);
        var i = /* @__PURE__ */ new Set();
        lv.length > 0 && (lv.forEach(function($) {
          i.add(ht($) || "Component"), kc.add($.type);
        }), lv = []);
        var l = /* @__PURE__ */ new Set();
        uv.length > 0 && (uv.forEach(function($) {
          l.add(ht($) || "Component"), kc.add($.type);
        }), uv = []);
        var c = /* @__PURE__ */ new Set();
        if (sv.length > 0 && (sv.forEach(function($) {
          c.add(ht($) || "Component"), kc.add($.type);
        }), sv = []), t.size > 0) {
          var p = _c(t);
          g(`Using UNSAFE_componentWillMount in strict mode is not recommended and may indicate bugs in your code. See https://reactjs.org/link/unsafe-component-lifecycles for details.

* Move code with side effects to componentDidMount, and set initial state in the constructor.

Please update the following components: %s`, p);
        }
        if (i.size > 0) {
          var m = _c(i);
          g(`Using UNSAFE_componentWillReceiveProps in strict mode is not recommended and may indicate bugs in your code. See https://reactjs.org/link/unsafe-component-lifecycles for details.

* Move data fetching code or side effects to componentDidUpdate.
* If you're updating state whenever props change, refactor your code to use memoization techniques or move it to static getDerivedStateFromProps. Learn more at: https://reactjs.org/link/derived-state

Please update the following components: %s`, m);
        }
        if (c.size > 0) {
          var E = _c(c);
          g(`Using UNSAFE_componentWillUpdate in strict mode is not recommended and may indicate bugs in your code. See https://reactjs.org/link/unsafe-component-lifecycles for details.

* Move data fetching code or side effects to componentDidUpdate.

Please update the following components: %s`, E);
        }
        if (e.size > 0) {
          var R = _c(e);
          _(`componentWillMount has been renamed, and is not recommended for use. See https://reactjs.org/link/unsafe-component-lifecycles for details.

* Move code with side effects to componentDidMount, and set initial state in the constructor.
* Rename componentWillMount to UNSAFE_componentWillMount to suppress this warning in non-strict mode. In React 18.x, only the UNSAFE_ name will work. To rename all deprecated lifecycles to their new names, you can run \`npx react-codemod rename-unsafe-lifecycles\` in your project source folder.

Please update the following components: %s`, R);
        }
        if (a.size > 0) {
          var w = _c(a);
          _(`componentWillReceiveProps has been renamed, and is not recommended for use. See https://reactjs.org/link/unsafe-component-lifecycles for details.

* Move data fetching code or side effects to componentDidUpdate.
* If you're updating state whenever props change, refactor your code to use memoization techniques or move it to static getDerivedStateFromProps. Learn more at: https://reactjs.org/link/derived-state
* Rename componentWillReceiveProps to UNSAFE_componentWillReceiveProps to suppress this warning in non-strict mode. In React 18.x, only the UNSAFE_ name will work. To rename all deprecated lifecycles to their new names, you can run \`npx react-codemod rename-unsafe-lifecycles\` in your project source folder.

Please update the following components: %s`, w);
        }
        if (l.size > 0) {
          var V = _c(l);
          _(`componentWillUpdate has been renamed, and is not recommended for use. See https://reactjs.org/link/unsafe-component-lifecycles for details.

* Move data fetching code or side effects to componentDidUpdate.
* Rename componentWillUpdate to UNSAFE_componentWillUpdate to suppress this warning in non-strict mode. In React 18.x, only the UNSAFE_ name will work. To rename all deprecated lifecycles to their new names, you can run \`npx react-codemod rename-unsafe-lifecycles\` in your project source folder.

Please update the following components: %s`, V);
        }
      };
      var Gm = /* @__PURE__ */ new Map(), Sb = /* @__PURE__ */ new Set();
      bo.recordLegacyContextWarning = function(e, t) {
        var a = q_(e);
        if (a === null) {
          g("Expected to find a StrictMode component in a strict mode tree. This error is likely caused by a bug in React. Please file an issue.");
          return;
        }
        if (!Sb.has(e.type)) {
          var i = Gm.get(a);
          (e.type.contextTypes != null || e.type.childContextTypes != null || t !== null && typeof t.getChildContext == "function") && (i === void 0 && (i = [], Gm.set(a, i)), i.push(e));
        }
      }, bo.flushLegacyContextWarning = function() {
        Gm.forEach(function(e, t) {
          if (e.length !== 0) {
            var a = e[0], i = /* @__PURE__ */ new Set();
            e.forEach(function(c) {
              i.add(ht(c) || "Component"), Sb.add(c.type);
            });
            var l = _c(i);
            try {
              on(a), g(`Legacy context API has been detected within a strict-mode tree.

The old API will be supported in all 16.x releases, but applications using it should migrate to the new version.

Please update the following components: %s

Learn more about this warning here: https://reactjs.org/link/legacy-context`, l);
            } finally {
              zn();
            }
          }
        });
      }, bo.discardPendingWarnings = function() {
        av = [], iv = [], ov = [], lv = [], uv = [], sv = [], Gm = /* @__PURE__ */ new Map();
      };
    }
    var M0, L0, z0, U0, P0, Eb = function(e, t) {
    };
    M0 = !1, L0 = !1, z0 = {}, U0 = {}, P0 = {}, Eb = function(e, t) {
      if (!(e === null || typeof e != "object") && !(!e._store || e._store.validated || e.key != null)) {
        if (typeof e._store != "object")
          throw new Error("React Component in warnForMissingKey should have a _store. This error is likely caused by a bug in React. Please file an issue.");
        e._store.validated = !0;
        var a = ht(t) || "Component";
        U0[a] || (U0[a] = !0, g('Each child in a list should have a unique "key" prop. See https://reactjs.org/link/warning-keys for more information.'));
      }
    };
    function K_(e) {
      return e.prototype && e.prototype.isReactComponent;
    }
    function cv(e, t, a) {
      var i = a.ref;
      if (i !== null && typeof i != "function" && typeof i != "object") {
        if ((e.mode & Ct || ye) && // We warn in ReactElement.js if owner and self are equal for string refs
        // because these cannot be automatically converted to an arrow function
        // using a codemod. Therefore, we don't have to warn about string refs again.
        !(a._owner && a._self && a._owner.stateNode !== a._self) && // Will already throw with "Function components cannot have string refs"
        !(a._owner && a._owner.tag !== A) && // Will already warn with "Function components cannot be given refs"
        !(typeof a.type == "function" && !K_(a.type)) && // Will already throw with "Element ref was specified as a string (someStringRef) but no owner was set"
        a._owner) {
          var l = ht(e) || "Component";
          z0[l] || (g('Component "%s" contains the string ref "%s". Support for string refs will be removed in a future major release. We recommend using useRef() or createRef() instead. Learn more about using refs safely here: https://reactjs.org/link/strict-mode-string-ref', l, i), z0[l] = !0);
        }
        if (a._owner) {
          var c = a._owner, p;
          if (c) {
            var m = c;
            if (m.tag !== A)
              throw new Error("Function components cannot have string refs. We recommend using useRef() instead. Learn more about using refs safely here: https://reactjs.org/link/strict-mode-string-ref");
            p = m.stateNode;
          }
          if (!p)
            throw new Error("Missing owner for string ref " + i + ". This error is likely caused by a bug in React. Please file an issue.");
          var E = p;
          di(i, "ref");
          var R = "" + i;
          if (t !== null && t.ref !== null && typeof t.ref == "function" && t.ref._stringRef === R)
            return t.ref;
          var w = function(V) {
            var $ = E.refs;
            V === null ? delete $[R] : $[R] = V;
          };
          return w._stringRef = R, w;
        } else {
          if (typeof i != "string")
            throw new Error("Expected ref to be a function, a string, an object returned by React.createRef(), or null.");
          if (!a._owner)
            throw new Error("Element ref was specified as a string (" + i + `) but no owner was set. This could happen for one of the following reasons:
1. You may be adding a ref to a function component
2. You may be adding a ref to a component that was not created inside a component's render method
3. You have multiple copies of React loaded
See https://reactjs.org/link/refs-must-have-owner for more information.`);
        }
      }
      return i;
    }
    function Qm(e, t) {
      var a = Object.prototype.toString.call(t);
      throw new Error("Objects are not valid as a React child (found: " + (a === "[object Object]" ? "object with keys {" + Object.keys(t).join(", ") + "}" : a) + "). If you meant to render a collection of children, use an array instead.");
    }
    function qm(e) {
      {
        var t = ht(e) || "Component";
        if (P0[t])
          return;
        P0[t] = !0, g("Functions are not valid as a React child. This may happen if you return a Component instead of <Component /> from render. Or maybe you meant to call this function rather than return it.");
      }
    }
    function Cb(e) {
      var t = e._payload, a = e._init;
      return a(t);
    }
    function bb(e) {
      function t(W, re) {
        if (e) {
          var G = W.deletions;
          G === null ? (W.deletions = [re], W.flags |= pa) : G.push(re);
        }
      }
      function a(W, re) {
        if (!e)
          return null;
        for (var G = re; G !== null; )
          t(W, G), G = G.sibling;
        return null;
      }
      function i(W, re) {
        for (var G = /* @__PURE__ */ new Map(), me = re; me !== null; )
          me.key !== null ? G.set(me.key, me) : G.set(me.index, me), me = me.sibling;
        return G;
      }
      function l(W, re) {
        var G = Pc(W, re);
        return G.index = 0, G.sibling = null, G;
      }
      function c(W, re, G) {
        if (W.index = G, !e)
          return W.flags |= Bs, re;
        var me = W.alternate;
        if (me !== null) {
          var We = me.index;
          return We < re ? (W.flags |= Kn, re) : We;
        } else
          return W.flags |= Kn, re;
      }
      function p(W) {
        return e && W.alternate === null && (W.flags |= Kn), W;
      }
      function m(W, re, G, me) {
        if (re === null || re.tag !== M) {
          var We = AE(G, W.mode, me);
          return We.return = W, We;
        } else {
          var Fe = l(re, G);
          return Fe.return = W, Fe;
        }
      }
      function E(W, re, G, me) {
        var We = G.type;
        if (We === ua)
          return w(W, re, G.props.children, me, G.key);
        if (re !== null && (re.elementType === We || // Keep this check inline so it only runs on the false path:
        _T(re, G) || // Lazy types should reconcile their resolved type.
        // We need to do this after the Hot Reloading check above,
        // because hot reloading has different semantics than prod because
        // it doesn't resuspend. So we can't let the call below suspend.
        typeof We == "object" && We !== null && We.$$typeof === yt && Cb(We) === re.type)) {
          var Fe = l(re, G.props);
          return Fe.ref = cv(W, re, G), Fe.return = W, Fe._debugSource = G._source, Fe._debugOwner = G._owner, Fe;
        }
        var dt = NE(G, W.mode, me);
        return dt.ref = cv(W, re, G), dt.return = W, dt;
      }
      function R(W, re, G, me) {
        if (re === null || re.tag !== te || re.stateNode.containerInfo !== G.containerInfo || re.stateNode.implementation !== G.implementation) {
          var We = ME(G, W.mode, me);
          return We.return = W, We;
        } else {
          var Fe = l(re, G.children || []);
          return Fe.return = W, Fe;
        }
      }
      function w(W, re, G, me, We) {
        if (re === null || re.tag !== j) {
          var Fe = ys(G, W.mode, me, We);
          return Fe.return = W, Fe;
        } else {
          var dt = l(re, G);
          return dt.return = W, dt;
        }
      }
      function V(W, re, G) {
        if (typeof re == "string" && re !== "" || typeof re == "number") {
          var me = AE("" + re, W.mode, G);
          return me.return = W, me;
        }
        if (typeof re == "object" && re !== null) {
          switch (re.$$typeof) {
            case Tr: {
              var We = NE(re, W.mode, G);
              return We.ref = cv(W, null, re), We.return = W, We;
            }
            case Na: {
              var Fe = ME(re, W.mode, G);
              return Fe.return = W, Fe;
            }
            case yt: {
              var dt = re._payload, St = re._init;
              return V(W, St(dt), G);
            }
          }
          if (bt(re) || Dn(re)) {
            var dn = ys(re, W.mode, G, null);
            return dn.return = W, dn;
          }
          Qm(W, re);
        }
        return typeof re == "function" && qm(W), null;
      }
      function $(W, re, G, me) {
        var We = re !== null ? re.key : null;
        if (typeof G == "string" && G !== "" || typeof G == "number")
          return We !== null ? null : m(W, re, "" + G, me);
        if (typeof G == "object" && G !== null) {
          switch (G.$$typeof) {
            case Tr:
              return G.key === We ? E(W, re, G, me) : null;
            case Na:
              return G.key === We ? R(W, re, G, me) : null;
            case yt: {
              var Fe = G._payload, dt = G._init;
              return $(W, re, dt(Fe), me);
            }
          }
          if (bt(G) || Dn(G))
            return We !== null ? null : w(W, re, G, me, null);
          Qm(W, G);
        }
        return typeof G == "function" && qm(W), null;
      }
      function X(W, re, G, me, We) {
        if (typeof me == "string" && me !== "" || typeof me == "number") {
          var Fe = W.get(G) || null;
          return m(re, Fe, "" + me, We);
        }
        if (typeof me == "object" && me !== null) {
          switch (me.$$typeof) {
            case Tr: {
              var dt = W.get(me.key === null ? G : me.key) || null;
              return E(re, dt, me, We);
            }
            case Na: {
              var St = W.get(me.key === null ? G : me.key) || null;
              return R(re, St, me, We);
            }
            case yt:
              var dn = me._payload, It = me._init;
              return X(W, re, G, It(dn), We);
          }
          if (bt(me) || Dn(me)) {
            var cr = W.get(G) || null;
            return w(re, cr, me, We, null);
          }
          Qm(re, me);
        }
        return typeof me == "function" && qm(re), null;
      }
      function Z(W, re, G) {
        {
          if (typeof W != "object" || W === null)
            return re;
          switch (W.$$typeof) {
            case Tr:
            case Na:
              Eb(W, G);
              var me = W.key;
              if (typeof me != "string")
                break;
              if (re === null) {
                re = /* @__PURE__ */ new Set(), re.add(me);
                break;
              }
              if (!re.has(me)) {
                re.add(me);
                break;
              }
              g("Encountered two children with the same key, `%s`. Keys should be unique so that components maintain their identity across updates. Non-unique keys may cause children to be duplicated and/or omitted — the behavior is unsupported and could change in a future version.", me);
              break;
            case yt:
              var We = W._payload, Fe = W._init;
              Z(Fe(We), re, G);
              break;
          }
        }
        return re;
      }
      function ne(W, re, G, me) {
        for (var We = null, Fe = 0; Fe < G.length; Fe++) {
          var dt = G[Fe];
          We = Z(dt, We, W);
        }
        for (var St = null, dn = null, It = re, cr = 0, Yt = 0, nr = null; It !== null && Yt < G.length; Yt++) {
          It.index > Yt ? (nr = It, It = null) : nr = It.sibling;
          var Ra = $(W, It, G[Yt], me);
          if (Ra === null) {
            It === null && (It = nr);
            break;
          }
          e && It && Ra.alternate === null && t(W, It), cr = c(Ra, cr, Yt), dn === null ? St = Ra : dn.sibling = Ra, dn = Ra, It = nr;
        }
        if (Yt === G.length) {
          if (a(W, It), Jr()) {
            var ia = Yt;
            Rc(W, ia);
          }
          return St;
        }
        if (It === null) {
          for (; Yt < G.length; Yt++) {
            var xi = V(W, G[Yt], me);
            xi !== null && (cr = c(xi, cr, Yt), dn === null ? St = xi : dn.sibling = xi, dn = xi);
          }
          if (Jr()) {
            var Va = Yt;
            Rc(W, Va);
          }
          return St;
        }
        for (var Ba = i(W, It); Yt < G.length; Yt++) {
          var wa = X(Ba, W, Yt, G[Yt], me);
          wa !== null && (e && wa.alternate !== null && Ba.delete(wa.key === null ? Yt : wa.key), cr = c(wa, cr, Yt), dn === null ? St = wa : dn.sibling = wa, dn = wa);
        }
        if (e && Ba.forEach(function(Od) {
          return t(W, Od);
        }), Jr()) {
          var fu = Yt;
          Rc(W, fu);
        }
        return St;
      }
      function Me(W, re, G, me) {
        var We = Dn(G);
        if (typeof We != "function")
          throw new Error("An object is not an iterable. This error is likely caused by a bug in React. Please file an issue.");
        {
          typeof Symbol == "function" && // $FlowFixMe Flow doesn't know about toStringTag
          G[Symbol.toStringTag] === "Generator" && (L0 || g("Using Generators as children is unsupported and will likely yield unexpected results because enumerating a generator mutates it. You may convert it to an array with `Array.from()` or the `[...spread]` operator before rendering. Keep in mind you might need to polyfill these features for older browsers."), L0 = !0), G.entries === We && (M0 || g("Using Maps as children is not supported. Use an array of keyed ReactElements instead."), M0 = !0);
          var Fe = We.call(G);
          if (Fe)
            for (var dt = null, St = Fe.next(); !St.done; St = Fe.next()) {
              var dn = St.value;
              dt = Z(dn, dt, W);
            }
        }
        var It = We.call(G);
        if (It == null)
          throw new Error("An iterable object provided no iterator.");
        for (var cr = null, Yt = null, nr = re, Ra = 0, ia = 0, xi = null, Va = It.next(); nr !== null && !Va.done; ia++, Va = It.next()) {
          nr.index > ia ? (xi = nr, nr = null) : xi = nr.sibling;
          var Ba = $(W, nr, Va.value, me);
          if (Ba === null) {
            nr === null && (nr = xi);
            break;
          }
          e && nr && Ba.alternate === null && t(W, nr), Ra = c(Ba, Ra, ia), Yt === null ? cr = Ba : Yt.sibling = Ba, Yt = Ba, nr = xi;
        }
        if (Va.done) {
          if (a(W, nr), Jr()) {
            var wa = ia;
            Rc(W, wa);
          }
          return cr;
        }
        if (nr === null) {
          for (; !Va.done; ia++, Va = It.next()) {
            var fu = V(W, Va.value, me);
            fu !== null && (Ra = c(fu, Ra, ia), Yt === null ? cr = fu : Yt.sibling = fu, Yt = fu);
          }
          if (Jr()) {
            var Od = ia;
            Rc(W, Od);
          }
          return cr;
        }
        for (var Vv = i(W, nr); !Va.done; ia++, Va = It.next()) {
          var vl = X(Vv, W, ia, Va.value, me);
          vl !== null && (e && vl.alternate !== null && Vv.delete(vl.key === null ? ia : vl.key), Ra = c(vl, Ra, ia), Yt === null ? cr = vl : Yt.sibling = vl, Yt = vl);
        }
        if (e && Vv.forEach(function(bN) {
          return t(W, bN);
        }), Jr()) {
          var CN = ia;
          Rc(W, CN);
        }
        return cr;
      }
      function lt(W, re, G, me) {
        if (re !== null && re.tag === M) {
          a(W, re.sibling);
          var We = l(re, G);
          return We.return = W, We;
        }
        a(W, re);
        var Fe = AE(G, W.mode, me);
        return Fe.return = W, Fe;
      }
      function tt(W, re, G, me) {
        for (var We = G.key, Fe = re; Fe !== null; ) {
          if (Fe.key === We) {
            var dt = G.type;
            if (dt === ua) {
              if (Fe.tag === j) {
                a(W, Fe.sibling);
                var St = l(Fe, G.props.children);
                return St.return = W, St._debugSource = G._source, St._debugOwner = G._owner, St;
              }
            } else if (Fe.elementType === dt || // Keep this check inline so it only runs on the false path:
            _T(Fe, G) || // Lazy types should reconcile their resolved type.
            // We need to do this after the Hot Reloading check above,
            // because hot reloading has different semantics than prod because
            // it doesn't resuspend. So we can't let the call below suspend.
            typeof dt == "object" && dt !== null && dt.$$typeof === yt && Cb(dt) === Fe.type) {
              a(W, Fe.sibling);
              var dn = l(Fe, G.props);
              return dn.ref = cv(W, Fe, G), dn.return = W, dn._debugSource = G._source, dn._debugOwner = G._owner, dn;
            }
            a(W, Fe);
            break;
          } else
            t(W, Fe);
          Fe = Fe.sibling;
        }
        if (G.type === ua) {
          var It = ys(G.props.children, W.mode, me, G.key);
          return It.return = W, It;
        } else {
          var cr = NE(G, W.mode, me);
          return cr.ref = cv(W, re, G), cr.return = W, cr;
        }
      }
      function jt(W, re, G, me) {
        for (var We = G.key, Fe = re; Fe !== null; ) {
          if (Fe.key === We)
            if (Fe.tag === te && Fe.stateNode.containerInfo === G.containerInfo && Fe.stateNode.implementation === G.implementation) {
              a(W, Fe.sibling);
              var dt = l(Fe, G.children || []);
              return dt.return = W, dt;
            } else {
              a(W, Fe);
              break;
            }
          else
            t(W, Fe);
          Fe = Fe.sibling;
        }
        var St = ME(G, W.mode, me);
        return St.return = W, St;
      }
      function Lt(W, re, G, me) {
        var We = typeof G == "object" && G !== null && G.type === ua && G.key === null;
        if (We && (G = G.props.children), typeof G == "object" && G !== null) {
          switch (G.$$typeof) {
            case Tr:
              return p(tt(W, re, G, me));
            case Na:
              return p(jt(W, re, G, me));
            case yt:
              var Fe = G._payload, dt = G._init;
              return Lt(W, re, dt(Fe), me);
          }
          if (bt(G))
            return ne(W, re, G, me);
          if (Dn(G))
            return Me(W, re, G, me);
          Qm(W, G);
        }
        return typeof G == "string" && G !== "" || typeof G == "number" ? p(lt(W, re, "" + G, me)) : (typeof G == "function" && qm(W), a(W, re));
      }
      return Lt;
    }
    var fd = bb(!0), Tb = bb(!1);
    function X_(e, t) {
      if (e !== null && t.child !== e.child)
        throw new Error("Resuming work not yet implemented.");
      if (t.child !== null) {
        var a = t.child, i = Pc(a, a.pendingProps);
        for (t.child = i, i.return = t; a.sibling !== null; )
          a = a.sibling, i = i.sibling = Pc(a, a.pendingProps), i.return = t;
        i.sibling = null;
      }
    }
    function J_(e, t) {
      for (var a = e.child; a !== null; )
        FD(a, t), a = a.sibling;
    }
    var $0 = rs(null), F0;
    F0 = {};
    var Km = null, dd = null, j0 = null, Xm = !1;
    function Jm() {
      Km = null, dd = null, j0 = null, Xm = !1;
    }
    function Rb() {
      Xm = !0;
    }
    function wb() {
      Xm = !1;
    }
    function xb(e, t, a) {
      ba($0, t._currentValue, e), t._currentValue = a, t._currentRenderer !== void 0 && t._currentRenderer !== null && t._currentRenderer !== F0 && g("Detected multiple renderers concurrently rendering the same context provider. This is currently unsupported."), t._currentRenderer = F0;
    }
    function H0(e, t) {
      var a = $0.current;
      Ca($0, t), e._currentValue = a;
    }
    function V0(e, t, a) {
      for (var i = e; i !== null; ) {
        var l = i.alternate;
        if (Bl(i.childLanes, t) ? l !== null && !Bl(l.childLanes, t) && (l.childLanes = Tt(l.childLanes, t)) : (i.childLanes = Tt(i.childLanes, t), l !== null && (l.childLanes = Tt(l.childLanes, t))), i === a)
          break;
        i = i.return;
      }
      i !== a && g("Expected to find the propagation root when scheduling context work. This error is likely caused by a bug in React. Please file an issue.");
    }
    function Z_(e, t, a) {
      ek(e, t, a);
    }
    function ek(e, t, a) {
      var i = e.child;
      for (i !== null && (i.return = e); i !== null; ) {
        var l = void 0, c = i.dependencies;
        if (c !== null) {
          l = i.child;
          for (var p = c.firstContext; p !== null; ) {
            if (p.context === t) {
              if (i.tag === A) {
                var m = gr(a), E = iu(tn, m);
                E.tag = ey;
                var R = i.updateQueue;
                if (R !== null) {
                  var w = R.shared, V = w.pending;
                  V === null ? E.next = E : (E.next = V.next, V.next = E), w.pending = E;
                }
              }
              i.lanes = Tt(i.lanes, a);
              var $ = i.alternate;
              $ !== null && ($.lanes = Tt($.lanes, a)), V0(i.return, a, e), c.lanes = Tt(c.lanes, a);
              break;
            }
            p = p.next;
          }
        } else if (i.tag === de)
          l = i.type === e.type ? null : i.child;
        else if (i.tag === ge) {
          var X = i.return;
          if (X === null)
            throw new Error("We just came from a parent so we must have had a parent. This is a bug in React.");
          X.lanes = Tt(X.lanes, a);
          var Z = X.alternate;
          Z !== null && (Z.lanes = Tt(Z.lanes, a)), V0(X, a, e), l = i.sibling;
        } else
          l = i.child;
        if (l !== null)
          l.return = i;
        else
          for (l = i; l !== null; ) {
            if (l === e) {
              l = null;
              break;
            }
            var ne = l.sibling;
            if (ne !== null) {
              ne.return = l.return, l = ne;
              break;
            }
            l = l.return;
          }
        i = l;
      }
    }
    function pd(e, t) {
      Km = e, dd = null, j0 = null;
      var a = e.dependencies;
      if (a !== null) {
        var i = a.firstContext;
        i !== null && (ga(a.lanes, t) && wv(), a.firstContext = null);
      }
    }
    function Er(e) {
      Xm && g("Context can only be read while React is rendering. In classes, you can read it in the render method or getDerivedStateFromProps. In function components, you can read it directly in the function body, but not inside Hooks like useReducer() or useMemo().");
      var t = e._currentValue;
      if (j0 !== e) {
        var a = {
          context: e,
          memoizedValue: t,
          next: null
        };
        if (dd === null) {
          if (Km === null)
            throw new Error("Context can only be read while React is rendering. In classes, you can read it in the render method or getDerivedStateFromProps. In function components, you can read it directly in the function body, but not inside Hooks like useReducer() or useMemo().");
          dd = a, Km.dependencies = {
            lanes: oe,
            firstContext: a
          };
        } else
          dd = dd.next = a;
      }
      return t;
    }
    var Oc = null;
    function B0(e) {
      Oc === null ? Oc = [e] : Oc.push(e);
    }
    function tk() {
      if (Oc !== null) {
        for (var e = 0; e < Oc.length; e++) {
          var t = Oc[e], a = t.interleaved;
          if (a !== null) {
            t.interleaved = null;
            var i = a.next, l = t.pending;
            if (l !== null) {
              var c = l.next;
              l.next = i, a.next = c;
            }
            t.pending = a;
          }
        }
        Oc = null;
      }
    }
    function _b(e, t, a, i) {
      var l = t.interleaved;
      return l === null ? (a.next = a, B0(t)) : (a.next = l.next, l.next = a), t.interleaved = a, Zm(e, i);
    }
    function nk(e, t, a, i) {
      var l = t.interleaved;
      l === null ? (a.next = a, B0(t)) : (a.next = l.next, l.next = a), t.interleaved = a;
    }
    function rk(e, t, a, i) {
      var l = t.interleaved;
      return l === null ? (a.next = a, B0(t)) : (a.next = l.next, l.next = a), t.interleaved = a, Zm(e, i);
    }
    function ii(e, t) {
      return Zm(e, t);
    }
    var ak = Zm;
    function Zm(e, t) {
      e.lanes = Tt(e.lanes, t);
      var a = e.alternate;
      a !== null && (a.lanes = Tt(a.lanes, t)), a === null && (e.flags & (Kn | Jn)) !== nt && TT(e);
      for (var i = e, l = e.return; l !== null; )
        l.childLanes = Tt(l.childLanes, t), a = l.alternate, a !== null ? a.childLanes = Tt(a.childLanes, t) : (l.flags & (Kn | Jn)) !== nt && TT(e), i = l, l = l.return;
      if (i.tag === U) {
        var c = i.stateNode;
        return c;
      } else
        return null;
    }
    var kb = 0, Ob = 1, ey = 2, I0 = 3, ty = !1, Y0, ny;
    Y0 = !1, ny = null;
    function W0(e) {
      var t = {
        baseState: e.memoizedState,
        firstBaseUpdate: null,
        lastBaseUpdate: null,
        shared: {
          pending: null,
          interleaved: null,
          lanes: oe
        },
        effects: null
      };
      e.updateQueue = t;
    }
    function Db(e, t) {
      var a = t.updateQueue, i = e.updateQueue;
      if (a === i) {
        var l = {
          baseState: i.baseState,
          firstBaseUpdate: i.firstBaseUpdate,
          lastBaseUpdate: i.lastBaseUpdate,
          shared: i.shared,
          effects: i.effects
        };
        t.updateQueue = l;
      }
    }
    function iu(e, t) {
      var a = {
        eventTime: e,
        lane: t,
        tag: kb,
        payload: null,
        callback: null,
        next: null
      };
      return a;
    }
    function ls(e, t, a) {
      var i = e.updateQueue;
      if (i === null)
        return null;
      var l = i.shared;
      if (ny === l && !Y0 && (g("An update (setState, replaceState, or forceUpdate) was scheduled from inside an update function. Update functions should be pure, with zero side-effects. Consider using componentDidUpdate or a callback."), Y0 = !0), nD()) {
        var c = l.pending;
        return c === null ? t.next = t : (t.next = c.next, c.next = t), l.pending = t, ak(e, a);
      } else
        return rk(e, l, t, a);
    }
    function ry(e, t, a) {
      var i = t.updateQueue;
      if (i !== null) {
        var l = i.shared;
        if (Rp(a)) {
          var c = l.lanes;
          c = Af(c, e.pendingLanes);
          var p = Tt(c, a);
          l.lanes = p, ic(e, p);
        }
      }
    }
    function G0(e, t) {
      var a = e.updateQueue, i = e.alternate;
      if (i !== null) {
        var l = i.updateQueue;
        if (a === l) {
          var c = null, p = null, m = a.firstBaseUpdate;
          if (m !== null) {
            var E = m;
            do {
              var R = {
                eventTime: E.eventTime,
                lane: E.lane,
                tag: E.tag,
                payload: E.payload,
                callback: E.callback,
                next: null
              };
              p === null ? c = p = R : (p.next = R, p = R), E = E.next;
            } while (E !== null);
            p === null ? c = p = t : (p.next = t, p = t);
          } else
            c = p = t;
          a = {
            baseState: l.baseState,
            firstBaseUpdate: c,
            lastBaseUpdate: p,
            shared: l.shared,
            effects: l.effects
          }, e.updateQueue = a;
          return;
        }
      }
      var w = a.lastBaseUpdate;
      w === null ? a.firstBaseUpdate = t : w.next = t, a.lastBaseUpdate = t;
    }
    function ik(e, t, a, i, l, c) {
      switch (a.tag) {
        case Ob: {
          var p = a.payload;
          if (typeof p == "function") {
            Rb();
            var m = p.call(c, i, l);
            {
              if (e.mode & Ct) {
                en(!0);
                try {
                  p.call(c, i, l);
                } finally {
                  en(!1);
                }
              }
              wb();
            }
            return m;
          }
          return p;
        }
        case I0:
          e.flags = e.flags & -65537 | Ot;
        case kb: {
          var E = a.payload, R;
          if (typeof E == "function") {
            Rb(), R = E.call(c, i, l);
            {
              if (e.mode & Ct) {
                en(!0);
                try {
                  E.call(c, i, l);
                } finally {
                  en(!1);
                }
              }
              wb();
            }
          } else
            R = E;
          return R == null ? i : Et({}, i, R);
        }
        case ey:
          return ty = !0, i;
      }
      return i;
    }
    function ay(e, t, a, i) {
      var l = e.updateQueue;
      ty = !1, ny = l.shared;
      var c = l.firstBaseUpdate, p = l.lastBaseUpdate, m = l.shared.pending;
      if (m !== null) {
        l.shared.pending = null;
        var E = m, R = E.next;
        E.next = null, p === null ? c = R : p.next = R, p = E;
        var w = e.alternate;
        if (w !== null) {
          var V = w.updateQueue, $ = V.lastBaseUpdate;
          $ !== p && ($ === null ? V.firstBaseUpdate = R : $.next = R, V.lastBaseUpdate = E);
        }
      }
      if (c !== null) {
        var X = l.baseState, Z = oe, ne = null, Me = null, lt = null, tt = c;
        do {
          var jt = tt.lane, Lt = tt.eventTime;
          if (Bl(i, jt)) {
            if (lt !== null) {
              var re = {
                eventTime: Lt,
                // This update is going to be committed so we never want uncommit
                // it. Using NoLane works because 0 is a subset of all bitmasks, so
                // this will never be skipped by the check above.
                lane: er,
                tag: tt.tag,
                payload: tt.payload,
                callback: tt.callback,
                next: null
              };
              lt = lt.next = re;
            }
            X = ik(e, l, tt, X, t, a);
            var G = tt.callback;
            if (G !== null && // If the update was already committed, we should not queue its
            // callback again.
            tt.lane !== er) {
              e.flags |= mn;
              var me = l.effects;
              me === null ? l.effects = [tt] : me.push(tt);
            }
          } else {
            var W = {
              eventTime: Lt,
              lane: jt,
              tag: tt.tag,
              payload: tt.payload,
              callback: tt.callback,
              next: null
            };
            lt === null ? (Me = lt = W, ne = X) : lt = lt.next = W, Z = Tt(Z, jt);
          }
          if (tt = tt.next, tt === null) {
            if (m = l.shared.pending, m === null)
              break;
            var We = m, Fe = We.next;
            We.next = null, tt = Fe, l.lastBaseUpdate = We, l.shared.pending = null;
          }
        } while (!0);
        lt === null && (ne = X), l.baseState = ne, l.firstBaseUpdate = Me, l.lastBaseUpdate = lt;
        var dt = l.shared.interleaved;
        if (dt !== null) {
          var St = dt;
          do
            Z = Tt(Z, St.lane), St = St.next;
          while (St !== dt);
        } else c === null && (l.shared.lanes = oe);
        Pv(Z), e.lanes = Z, e.memoizedState = X;
      }
      ny = null;
    }
    function ok(e, t) {
      if (typeof e != "function")
        throw new Error("Invalid argument passed as callback. Expected a function. Instead " + ("received: " + e));
      e.call(t);
    }
    function Nb() {
      ty = !1;
    }
    function iy() {
      return ty;
    }
    function Ab(e, t, a) {
      var i = t.effects;
      if (t.effects = null, i !== null)
        for (var l = 0; l < i.length; l++) {
          var c = i[l], p = c.callback;
          p !== null && (c.callback = null, ok(p, a));
        }
    }
    var fv = {}, us = rs(fv), dv = rs(fv), oy = rs(fv);
    function ly(e) {
      if (e === fv)
        throw new Error("Expected host context to exist. This error is likely caused by a bug in React. Please file an issue.");
      return e;
    }
    function Mb() {
      var e = ly(oy.current);
      return e;
    }
    function Q0(e, t) {
      ba(oy, t, e), ba(dv, e, e), ba(us, fv, e);
      var a = Tx(t);
      Ca(us, e), ba(us, a, e);
    }
    function vd(e) {
      Ca(us, e), Ca(dv, e), Ca(oy, e);
    }
    function q0() {
      var e = ly(us.current);
      return e;
    }
    function Lb(e) {
      ly(oy.current);
      var t = ly(us.current), a = Rx(t, e.type);
      t !== a && (ba(dv, e, e), ba(us, a, e));
    }
    function K0(e) {
      dv.current === e && (Ca(us, e), Ca(dv, e));
    }
    var lk = 0, zb = 1, Ub = 1, pv = 2, To = rs(lk);
    function X0(e, t) {
      return (e & t) !== 0;
    }
    function hd(e) {
      return e & zb;
    }
    function J0(e, t) {
      return e & zb | t;
    }
    function uk(e, t) {
      return e | t;
    }
    function ss(e, t) {
      ba(To, t, e);
    }
    function md(e) {
      Ca(To, e);
    }
    function sk(e, t) {
      var a = e.memoizedState;
      return a !== null ? a.dehydrated !== null : (e.memoizedProps, !0);
    }
    function uy(e) {
      for (var t = e; t !== null; ) {
        if (t.tag === se) {
          var a = t.memoizedState;
          if (a !== null) {
            var i = a.dehydrated;
            if (i === null || ZC(i) || m0(i))
              return t;
          }
        } else if (t.tag === je && // revealOrder undefined can't be trusted because it don't
        // keep track of whether it suspended or not.
        t.memoizedProps.revealOrder !== void 0) {
          var l = (t.flags & Ot) !== nt;
          if (l)
            return t;
        } else if (t.child !== null) {
          t.child.return = t, t = t.child;
          continue;
        }
        if (t === e)
          return null;
        for (; t.sibling === null; ) {
          if (t.return === null || t.return === e)
            return null;
          t = t.return;
        }
        t.sibling.return = t.return, t = t.sibling;
      }
      return null;
    }
    var oi = (
      /*   */
      0
    ), Or = (
      /* */
      1
    ), ll = (
      /*  */
      2
    ), Dr = (
      /*    */
      4
    ), Zr = (
      /*   */
      8
    ), Z0 = [];
    function eS() {
      for (var e = 0; e < Z0.length; e++) {
        var t = Z0[e];
        t._workInProgressVersionPrimary = null;
      }
      Z0.length = 0;
    }
    function ck(e, t) {
      var a = t._getVersion, i = a(t._source);
      e.mutableSourceEagerHydrationData == null ? e.mutableSourceEagerHydrationData = [t, i] : e.mutableSourceEagerHydrationData.push(t, i);
    }
    var Be = y.ReactCurrentDispatcher, vv = y.ReactCurrentBatchConfig, tS, yd;
    tS = /* @__PURE__ */ new Set();
    var Dc = oe, fn = null, Nr = null, Ar = null, sy = !1, hv = !1, mv = 0, fk = 0, dk = 25, le = null, Qi = null, cs = -1, nS = !1;
    function Jt() {
      {
        var e = le;
        Qi === null ? Qi = [e] : Qi.push(e);
      }
    }
    function Oe() {
      {
        var e = le;
        Qi !== null && (cs++, Qi[cs] !== e && pk(e));
      }
    }
    function gd(e) {
      e != null && !bt(e) && g("%s received a final argument that is not an array (instead, received `%s`). When specified, the final argument must be an array.", le, typeof e);
    }
    function pk(e) {
      {
        var t = ht(fn);
        if (!tS.has(t) && (tS.add(t), Qi !== null)) {
          for (var a = "", i = 30, l = 0; l <= cs; l++) {
            for (var c = Qi[l], p = l === cs ? e : c, m = l + 1 + ". " + c; m.length < i; )
              m += " ";
            m += p + `
`, a += m;
          }
          g(`React has detected a change in the order of Hooks called by %s. This will lead to bugs and errors if not fixed. For more information, read the Rules of Hooks: https://reactjs.org/link/rules-of-hooks

   Previous render            Next render
   ------------------------------------------------------
%s   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
`, t, a);
        }
      }
    }
    function Ta() {
      throw new Error(`Invalid hook call. Hooks can only be called inside of the body of a function component. This could happen for one of the following reasons:
1. You might have mismatching versions of React and the renderer (such as React DOM)
2. You might be breaking the Rules of Hooks
3. You might have more than one copy of React in the same app
See https://reactjs.org/link/invalid-hook-call for tips about how to debug and fix this problem.`);
    }
    function rS(e, t) {
      if (nS)
        return !1;
      if (t === null)
        return g("%s received a final argument during this render, but not during the previous render. Even though the final argument is optional, its type cannot change between renders.", le), !1;
      e.length !== t.length && g(`The final argument passed to %s changed size between renders. The order and size of this array must remain constant.

Previous: %s
Incoming: %s`, le, "[" + t.join(", ") + "]", "[" + e.join(", ") + "]");
      for (var a = 0; a < t.length && a < e.length; a++)
        if (!$e(e[a], t[a]))
          return !1;
      return !0;
    }
    function Sd(e, t, a, i, l, c) {
      Dc = c, fn = t, Qi = e !== null ? e._debugHookTypes : null, cs = -1, nS = e !== null && e.type !== t.type, t.memoizedState = null, t.updateQueue = null, t.lanes = oe, e !== null && e.memoizedState !== null ? Be.current = a1 : Qi !== null ? Be.current = r1 : Be.current = n1;
      var p = a(i, l);
      if (hv) {
        var m = 0;
        do {
          if (hv = !1, mv = 0, m >= dk)
            throw new Error("Too many re-renders. React limits the number of renders to prevent an infinite loop.");
          m += 1, nS = !1, Nr = null, Ar = null, t.updateQueue = null, cs = -1, Be.current = i1, p = a(i, l);
        } while (hv);
      }
      Be.current = by, t._debugHookTypes = Qi;
      var E = Nr !== null && Nr.next !== null;
      if (Dc = oe, fn = null, Nr = null, Ar = null, le = null, Qi = null, cs = -1, e !== null && (e.flags & Zn) !== (t.flags & Zn) && // Disable this warning in legacy mode, because legacy Suspense is weird
      // and creates false positives. To make this work in legacy mode, we'd
      // need to mark fibers that commit in an incomplete state, somehow. For
      // now I'll disable the warning that most of the bugs that would trigger
      // it are either exclusive to concurrent mode or exist in both.
      (e.mode & Dt) !== rt && g("Internal React error: Expected static flag was missing. Please notify the React team."), sy = !1, E)
        throw new Error("Rendered fewer hooks than expected. This may be caused by an accidental early return statement.");
      return p;
    }
    function Ed() {
      var e = mv !== 0;
      return mv = 0, e;
    }
    function Pb(e, t, a) {
      t.updateQueue = e.updateQueue, (t.mode & cn) !== rt ? t.flags &= -50333701 : t.flags &= -2053, e.lanes = ac(e.lanes, a);
    }
    function $b() {
      if (Be.current = by, sy) {
        for (var e = fn.memoizedState; e !== null; ) {
          var t = e.queue;
          t !== null && (t.pending = null), e = e.next;
        }
        sy = !1;
      }
      Dc = oe, fn = null, Nr = null, Ar = null, Qi = null, cs = -1, le = null, Xb = !1, hv = !1, mv = 0;
    }
    function ul() {
      var e = {
        memoizedState: null,
        baseState: null,
        baseQueue: null,
        queue: null,
        next: null
      };
      return Ar === null ? fn.memoizedState = Ar = e : Ar = Ar.next = e, Ar;
    }
    function qi() {
      var e;
      if (Nr === null) {
        var t = fn.alternate;
        t !== null ? e = t.memoizedState : e = null;
      } else
        e = Nr.next;
      var a;
      if (Ar === null ? a = fn.memoizedState : a = Ar.next, a !== null)
        Ar = a, a = Ar.next, Nr = e;
      else {
        if (e === null)
          throw new Error("Rendered more hooks than during the previous render.");
        Nr = e;
        var i = {
          memoizedState: Nr.memoizedState,
          baseState: Nr.baseState,
          baseQueue: Nr.baseQueue,
          queue: Nr.queue,
          next: null
        };
        Ar === null ? fn.memoizedState = Ar = i : Ar = Ar.next = i;
      }
      return Ar;
    }
    function Fb() {
      return {
        lastEffect: null,
        stores: null
      };
    }
    function aS(e, t) {
      return typeof t == "function" ? t(e) : t;
    }
    function iS(e, t, a) {
      var i = ul(), l;
      a !== void 0 ? l = a(t) : l = t, i.memoizedState = i.baseState = l;
      var c = {
        pending: null,
        interleaved: null,
        lanes: oe,
        dispatch: null,
        lastRenderedReducer: e,
        lastRenderedState: l
      };
      i.queue = c;
      var p = c.dispatch = yk.bind(null, fn, c);
      return [i.memoizedState, p];
    }
    function oS(e, t, a) {
      var i = qi(), l = i.queue;
      if (l === null)
        throw new Error("Should have a queue. This is likely a bug in React. Please file an issue.");
      l.lastRenderedReducer = e;
      var c = Nr, p = c.baseQueue, m = l.pending;
      if (m !== null) {
        if (p !== null) {
          var E = p.next, R = m.next;
          p.next = R, m.next = E;
        }
        c.baseQueue !== p && g("Internal error: Expected work-in-progress queue to be a clone. This is a bug in React."), c.baseQueue = p = m, l.pending = null;
      }
      if (p !== null) {
        var w = p.next, V = c.baseState, $ = null, X = null, Z = null, ne = w;
        do {
          var Me = ne.lane;
          if (Bl(Dc, Me)) {
            if (Z !== null) {
              var tt = {
                // This update is going to be committed so we never want uncommit
                // it. Using NoLane works because 0 is a subset of all bitmasks, so
                // this will never be skipped by the check above.
                lane: er,
                action: ne.action,
                hasEagerState: ne.hasEagerState,
                eagerState: ne.eagerState,
                next: null
              };
              Z = Z.next = tt;
            }
            if (ne.hasEagerState)
              V = ne.eagerState;
            else {
              var jt = ne.action;
              V = e(V, jt);
            }
          } else {
            var lt = {
              lane: Me,
              action: ne.action,
              hasEagerState: ne.hasEagerState,
              eagerState: ne.eagerState,
              next: null
            };
            Z === null ? (X = Z = lt, $ = V) : Z = Z.next = lt, fn.lanes = Tt(fn.lanes, Me), Pv(Me);
          }
          ne = ne.next;
        } while (ne !== null && ne !== w);
        Z === null ? $ = V : Z.next = X, $e(V, i.memoizedState) || wv(), i.memoizedState = V, i.baseState = $, i.baseQueue = Z, l.lastRenderedState = V;
      }
      var Lt = l.interleaved;
      if (Lt !== null) {
        var W = Lt;
        do {
          var re = W.lane;
          fn.lanes = Tt(fn.lanes, re), Pv(re), W = W.next;
        } while (W !== Lt);
      } else p === null && (l.lanes = oe);
      var G = l.dispatch;
      return [i.memoizedState, G];
    }
    function lS(e, t, a) {
      var i = qi(), l = i.queue;
      if (l === null)
        throw new Error("Should have a queue. This is likely a bug in React. Please file an issue.");
      l.lastRenderedReducer = e;
      var c = l.dispatch, p = l.pending, m = i.memoizedState;
      if (p !== null) {
        l.pending = null;
        var E = p.next, R = E;
        do {
          var w = R.action;
          m = e(m, w), R = R.next;
        } while (R !== E);
        $e(m, i.memoizedState) || wv(), i.memoizedState = m, i.baseQueue === null && (i.baseState = m), l.lastRenderedState = m;
      }
      return [m, c];
    }
    function zz(e, t, a) {
    }
    function Uz(e, t, a) {
    }
    function uS(e, t, a) {
      var i = fn, l = ul(), c, p = Jr();
      if (p) {
        if (a === void 0)
          throw new Error("Missing getServerSnapshot, which is required for server-rendered content. Will revert to client rendering.");
        c = a(), yd || c !== a() && (g("The result of getServerSnapshot should be cached to avoid an infinite loop"), yd = !0);
      } else {
        if (c = t(), !yd) {
          var m = t();
          $e(c, m) || (g("The result of getSnapshot should be cached to avoid an infinite loop"), yd = !0);
        }
        var E = Hy();
        if (E === null)
          throw new Error("Expected a work-in-progress root. This is a bug in React. Please file an issue.");
        rc(E, Dc) || jb(i, t, c);
      }
      l.memoizedState = c;
      var R = {
        value: c,
        getSnapshot: t
      };
      return l.queue = R, vy(Vb.bind(null, i, R, e), [e]), i.flags |= Aa, yv(Or | Zr, Hb.bind(null, i, R, c, t), void 0, null), c;
    }
    function cy(e, t, a) {
      var i = fn, l = qi(), c = t();
      if (!yd) {
        var p = t();
        $e(c, p) || (g("The result of getSnapshot should be cached to avoid an infinite loop"), yd = !0);
      }
      var m = l.memoizedState, E = !$e(m, c);
      E && (l.memoizedState = c, wv());
      var R = l.queue;
      if (Sv(Vb.bind(null, i, R, e), [e]), R.getSnapshot !== t || E || // Check if the susbcribe function changed. We can save some memory by
      // checking whether we scheduled a subscription effect above.
      Ar !== null && Ar.memoizedState.tag & Or) {
        i.flags |= Aa, yv(Or | Zr, Hb.bind(null, i, R, c, t), void 0, null);
        var w = Hy();
        if (w === null)
          throw new Error("Expected a work-in-progress root. This is a bug in React. Please file an issue.");
        rc(w, Dc) || jb(i, t, c);
      }
      return c;
    }
    function jb(e, t, a) {
      e.flags |= of;
      var i = {
        getSnapshot: t,
        value: a
      }, l = fn.updateQueue;
      if (l === null)
        l = Fb(), fn.updateQueue = l, l.stores = [i];
      else {
        var c = l.stores;
        c === null ? l.stores = [i] : c.push(i);
      }
    }
    function Hb(e, t, a, i) {
      t.value = a, t.getSnapshot = i, Bb(t) && Ib(e);
    }
    function Vb(e, t, a) {
      var i = function() {
        Bb(t) && Ib(e);
      };
      return a(i);
    }
    function Bb(e) {
      var t = e.getSnapshot, a = e.value;
      try {
        var i = t();
        return !$e(a, i);
      } catch {
        return !0;
      }
    }
    function Ib(e) {
      var t = ii(e, ct);
      t !== null && Ur(t, e, ct, tn);
    }
    function fy(e) {
      var t = ul();
      typeof e == "function" && (e = e()), t.memoizedState = t.baseState = e;
      var a = {
        pending: null,
        interleaved: null,
        lanes: oe,
        dispatch: null,
        lastRenderedReducer: aS,
        lastRenderedState: e
      };
      t.queue = a;
      var i = a.dispatch = gk.bind(null, fn, a);
      return [t.memoizedState, i];
    }
    function sS(e) {
      return oS(aS);
    }
    function cS(e) {
      return lS(aS);
    }
    function yv(e, t, a, i) {
      var l = {
        tag: e,
        create: t,
        destroy: a,
        deps: i,
        // Circular
        next: null
      }, c = fn.updateQueue;
      if (c === null)
        c = Fb(), fn.updateQueue = c, c.lastEffect = l.next = l;
      else {
        var p = c.lastEffect;
        if (p === null)
          c.lastEffect = l.next = l;
        else {
          var m = p.next;
          p.next = l, l.next = m, c.lastEffect = l;
        }
      }
      return l;
    }
    function fS(e) {
      var t = ul();
      {
        var a = {
          current: e
        };
        return t.memoizedState = a, a;
      }
    }
    function dy(e) {
      var t = qi();
      return t.memoizedState;
    }
    function gv(e, t, a, i) {
      var l = ul(), c = i === void 0 ? null : i;
      fn.flags |= e, l.memoizedState = yv(Or | t, a, void 0, c);
    }
    function py(e, t, a, i) {
      var l = qi(), c = i === void 0 ? null : i, p = void 0;
      if (Nr !== null) {
        var m = Nr.memoizedState;
        if (p = m.destroy, c !== null) {
          var E = m.deps;
          if (rS(c, E)) {
            l.memoizedState = yv(t, a, p, c);
            return;
          }
        }
      }
      fn.flags |= e, l.memoizedState = yv(Or | t, a, p, c);
    }
    function vy(e, t) {
      return (fn.mode & cn) !== rt ? gv(Ho | Aa | ap, Zr, e, t) : gv(Aa | ap, Zr, e, t);
    }
    function Sv(e, t) {
      return py(Aa, Zr, e, t);
    }
    function dS(e, t) {
      return gv(At, ll, e, t);
    }
    function hy(e, t) {
      return py(At, ll, e, t);
    }
    function pS(e, t) {
      var a = At;
      return a |= jo, (fn.mode & cn) !== rt && (a |= Qr), gv(a, Dr, e, t);
    }
    function my(e, t) {
      return py(At, Dr, e, t);
    }
    function Yb(e, t) {
      if (typeof t == "function") {
        var a = t, i = e();
        return a(i), function() {
          a(null);
        };
      } else if (t != null) {
        var l = t;
        l.hasOwnProperty("current") || g("Expected useImperativeHandle() first argument to either be a ref callback or React.createRef() object. Instead received: %s.", "an object with keys {" + Object.keys(l).join(", ") + "}");
        var c = e();
        return l.current = c, function() {
          l.current = null;
        };
      }
    }
    function vS(e, t, a) {
      typeof t != "function" && g("Expected useImperativeHandle() second argument to be a function that creates a handle. Instead received: %s.", t !== null ? typeof t : "null");
      var i = a != null ? a.concat([e]) : null, l = At;
      return l |= jo, (fn.mode & cn) !== rt && (l |= Qr), gv(l, Dr, Yb.bind(null, t, e), i);
    }
    function yy(e, t, a) {
      typeof t != "function" && g("Expected useImperativeHandle() second argument to be a function that creates a handle. Instead received: %s.", t !== null ? typeof t : "null");
      var i = a != null ? a.concat([e]) : null;
      return py(At, Dr, Yb.bind(null, t, e), i);
    }
    function vk(e, t) {
    }
    var gy = vk;
    function hS(e, t) {
      var a = ul(), i = t === void 0 ? null : t;
      return a.memoizedState = [e, i], e;
    }
    function Sy(e, t) {
      var a = qi(), i = t === void 0 ? null : t, l = a.memoizedState;
      if (l !== null && i !== null) {
        var c = l[1];
        if (rS(i, c))
          return l[0];
      }
      return a.memoizedState = [e, i], e;
    }
    function mS(e, t) {
      var a = ul(), i = t === void 0 ? null : t, l = e();
      return a.memoizedState = [l, i], l;
    }
    function Ey(e, t) {
      var a = qi(), i = t === void 0 ? null : t, l = a.memoizedState;
      if (l !== null && i !== null) {
        var c = l[1];
        if (rS(i, c))
          return l[0];
      }
      var p = e();
      return a.memoizedState = [p, i], p;
    }
    function yS(e) {
      var t = ul();
      return t.memoizedState = e, e;
    }
    function Wb(e) {
      var t = qi(), a = Nr, i = a.memoizedState;
      return Qb(t, i, e);
    }
    function Gb(e) {
      var t = qi();
      if (Nr === null)
        return t.memoizedState = e, e;
      var a = Nr.memoizedState;
      return Qb(t, a, e);
    }
    function Qb(e, t, a) {
      var i = !Tp(Dc);
      if (i) {
        if (!$e(a, t)) {
          var l = wp();
          fn.lanes = Tt(fn.lanes, l), Pv(l), e.baseState = !0;
        }
        return t;
      } else
        return e.baseState && (e.baseState = !1, wv()), e.memoizedState = a, a;
    }
    function hk(e, t, a) {
      var i = za();
      lr(oc(i, ei)), e(!0);
      var l = vv.transition;
      vv.transition = {};
      var c = vv.transition;
      vv.transition._updatedFibers = /* @__PURE__ */ new Set();
      try {
        e(!1), t();
      } finally {
        if (lr(i), vv.transition = l, l === null && c._updatedFibers) {
          var p = c._updatedFibers.size;
          p > 10 && _("Detected a large number of updates inside startTransition. If this is due to a subscription please re-write it to use React provided hooks. Otherwise concurrent mode guarantees are off the table."), c._updatedFibers.clear();
        }
      }
    }
    function gS() {
      var e = fy(!1), t = e[0], a = e[1], i = hk.bind(null, a), l = ul();
      return l.memoizedState = i, [t, i];
    }
    function qb() {
      var e = sS(), t = e[0], a = qi(), i = a.memoizedState;
      return [t, i];
    }
    function Kb() {
      var e = cS(), t = e[0], a = qi(), i = a.memoizedState;
      return [t, i];
    }
    var Xb = !1;
    function mk() {
      return Xb;
    }
    function SS() {
      var e = ul(), t = Hy(), a = t.identifierPrefix, i;
      if (Jr()) {
        var l = M_();
        i = ":" + a + "R" + l;
        var c = mv++;
        c > 0 && (i += "H" + c.toString(32)), i += ":";
      } else {
        var p = fk++;
        i = ":" + a + "r" + p.toString(32) + ":";
      }
      return e.memoizedState = i, i;
    }
    function Cy() {
      var e = qi(), t = e.memoizedState;
      return t;
    }
    function yk(e, t, a) {
      typeof arguments[3] == "function" && g("State updates from the useState() and useReducer() Hooks don't support the second callback argument. To execute a side effect after rendering, declare it in the component body with useEffect().");
      var i = hs(e), l = {
        lane: i,
        action: a,
        hasEagerState: !1,
        eagerState: null,
        next: null
      };
      if (Jb(e))
        Zb(t, l);
      else {
        var c = _b(e, t, l, i);
        if (c !== null) {
          var p = Ha();
          Ur(c, e, i, p), e1(c, t, i);
        }
      }
      t1(e, i);
    }
    function gk(e, t, a) {
      typeof arguments[3] == "function" && g("State updates from the useState() and useReducer() Hooks don't support the second callback argument. To execute a side effect after rendering, declare it in the component body with useEffect().");
      var i = hs(e), l = {
        lane: i,
        action: a,
        hasEagerState: !1,
        eagerState: null,
        next: null
      };
      if (Jb(e))
        Zb(t, l);
      else {
        var c = e.alternate;
        if (e.lanes === oe && (c === null || c.lanes === oe)) {
          var p = t.lastRenderedReducer;
          if (p !== null) {
            var m;
            m = Be.current, Be.current = Ro;
            try {
              var E = t.lastRenderedState, R = p(E, a);
              if (l.hasEagerState = !0, l.eagerState = R, $e(R, E)) {
                nk(e, t, l, i);
                return;
              }
            } catch {
            } finally {
              Be.current = m;
            }
          }
        }
        var w = _b(e, t, l, i);
        if (w !== null) {
          var V = Ha();
          Ur(w, e, i, V), e1(w, t, i);
        }
      }
      t1(e, i);
    }
    function Jb(e) {
      var t = e.alternate;
      return e === fn || t !== null && t === fn;
    }
    function Zb(e, t) {
      hv = sy = !0;
      var a = e.pending;
      a === null ? t.next = t : (t.next = a.next, a.next = t), e.pending = t;
    }
    function e1(e, t, a) {
      if (Rp(a)) {
        var i = t.lanes;
        i = Af(i, e.pendingLanes);
        var l = Tt(i, a);
        t.lanes = l, ic(e, l);
      }
    }
    function t1(e, t, a) {
      qs(e, t);
    }
    var by = {
      readContext: Er,
      useCallback: Ta,
      useContext: Ta,
      useEffect: Ta,
      useImperativeHandle: Ta,
      useInsertionEffect: Ta,
      useLayoutEffect: Ta,
      useMemo: Ta,
      useReducer: Ta,
      useRef: Ta,
      useState: Ta,
      useDebugValue: Ta,
      useDeferredValue: Ta,
      useTransition: Ta,
      useMutableSource: Ta,
      useSyncExternalStore: Ta,
      useId: Ta,
      unstable_isNewReconciler: Ie
    }, n1 = null, r1 = null, a1 = null, i1 = null, sl = null, Ro = null, Ty = null;
    {
      var ES = function() {
        g("Context can only be read while React is rendering. In classes, you can read it in the render method or getDerivedStateFromProps. In function components, you can read it directly in the function body, but not inside Hooks like useReducer() or useMemo().");
      }, gt = function() {
        g("Do not call Hooks inside useEffect(...), useMemo(...), or other built-in Hooks. You can only call Hooks at the top level of your React function. For more information, see https://reactjs.org/link/rules-of-hooks");
      };
      n1 = {
        readContext: function(e) {
          return Er(e);
        },
        useCallback: function(e, t) {
          return le = "useCallback", Jt(), gd(t), hS(e, t);
        },
        useContext: function(e) {
          return le = "useContext", Jt(), Er(e);
        },
        useEffect: function(e, t) {
          return le = "useEffect", Jt(), gd(t), vy(e, t);
        },
        useImperativeHandle: function(e, t, a) {
          return le = "useImperativeHandle", Jt(), gd(a), vS(e, t, a);
        },
        useInsertionEffect: function(e, t) {
          return le = "useInsertionEffect", Jt(), gd(t), dS(e, t);
        },
        useLayoutEffect: function(e, t) {
          return le = "useLayoutEffect", Jt(), gd(t), pS(e, t);
        },
        useMemo: function(e, t) {
          le = "useMemo", Jt(), gd(t);
          var a = Be.current;
          Be.current = sl;
          try {
            return mS(e, t);
          } finally {
            Be.current = a;
          }
        },
        useReducer: function(e, t, a) {
          le = "useReducer", Jt();
          var i = Be.current;
          Be.current = sl;
          try {
            return iS(e, t, a);
          } finally {
            Be.current = i;
          }
        },
        useRef: function(e) {
          return le = "useRef", Jt(), fS(e);
        },
        useState: function(e) {
          le = "useState", Jt();
          var t = Be.current;
          Be.current = sl;
          try {
            return fy(e);
          } finally {
            Be.current = t;
          }
        },
        useDebugValue: function(e, t) {
          return le = "useDebugValue", Jt(), void 0;
        },
        useDeferredValue: function(e) {
          return le = "useDeferredValue", Jt(), yS(e);
        },
        useTransition: function() {
          return le = "useTransition", Jt(), gS();
        },
        useMutableSource: function(e, t, a) {
          return le = "useMutableSource", Jt(), void 0;
        },
        useSyncExternalStore: function(e, t, a) {
          return le = "useSyncExternalStore", Jt(), uS(e, t, a);
        },
        useId: function() {
          return le = "useId", Jt(), SS();
        },
        unstable_isNewReconciler: Ie
      }, r1 = {
        readContext: function(e) {
          return Er(e);
        },
        useCallback: function(e, t) {
          return le = "useCallback", Oe(), hS(e, t);
        },
        useContext: function(e) {
          return le = "useContext", Oe(), Er(e);
        },
        useEffect: function(e, t) {
          return le = "useEffect", Oe(), vy(e, t);
        },
        useImperativeHandle: function(e, t, a) {
          return le = "useImperativeHandle", Oe(), vS(e, t, a);
        },
        useInsertionEffect: function(e, t) {
          return le = "useInsertionEffect", Oe(), dS(e, t);
        },
        useLayoutEffect: function(e, t) {
          return le = "useLayoutEffect", Oe(), pS(e, t);
        },
        useMemo: function(e, t) {
          le = "useMemo", Oe();
          var a = Be.current;
          Be.current = sl;
          try {
            return mS(e, t);
          } finally {
            Be.current = a;
          }
        },
        useReducer: function(e, t, a) {
          le = "useReducer", Oe();
          var i = Be.current;
          Be.current = sl;
          try {
            return iS(e, t, a);
          } finally {
            Be.current = i;
          }
        },
        useRef: function(e) {
          return le = "useRef", Oe(), fS(e);
        },
        useState: function(e) {
          le = "useState", Oe();
          var t = Be.current;
          Be.current = sl;
          try {
            return fy(e);
          } finally {
            Be.current = t;
          }
        },
        useDebugValue: function(e, t) {
          return le = "useDebugValue", Oe(), void 0;
        },
        useDeferredValue: function(e) {
          return le = "useDeferredValue", Oe(), yS(e);
        },
        useTransition: function() {
          return le = "useTransition", Oe(), gS();
        },
        useMutableSource: function(e, t, a) {
          return le = "useMutableSource", Oe(), void 0;
        },
        useSyncExternalStore: function(e, t, a) {
          return le = "useSyncExternalStore", Oe(), uS(e, t, a);
        },
        useId: function() {
          return le = "useId", Oe(), SS();
        },
        unstable_isNewReconciler: Ie
      }, a1 = {
        readContext: function(e) {
          return Er(e);
        },
        useCallback: function(e, t) {
          return le = "useCallback", Oe(), Sy(e, t);
        },
        useContext: function(e) {
          return le = "useContext", Oe(), Er(e);
        },
        useEffect: function(e, t) {
          return le = "useEffect", Oe(), Sv(e, t);
        },
        useImperativeHandle: function(e, t, a) {
          return le = "useImperativeHandle", Oe(), yy(e, t, a);
        },
        useInsertionEffect: function(e, t) {
          return le = "useInsertionEffect", Oe(), hy(e, t);
        },
        useLayoutEffect: function(e, t) {
          return le = "useLayoutEffect", Oe(), my(e, t);
        },
        useMemo: function(e, t) {
          le = "useMemo", Oe();
          var a = Be.current;
          Be.current = Ro;
          try {
            return Ey(e, t);
          } finally {
            Be.current = a;
          }
        },
        useReducer: function(e, t, a) {
          le = "useReducer", Oe();
          var i = Be.current;
          Be.current = Ro;
          try {
            return oS(e, t, a);
          } finally {
            Be.current = i;
          }
        },
        useRef: function(e) {
          return le = "useRef", Oe(), dy();
        },
        useState: function(e) {
          le = "useState", Oe();
          var t = Be.current;
          Be.current = Ro;
          try {
            return sS(e);
          } finally {
            Be.current = t;
          }
        },
        useDebugValue: function(e, t) {
          return le = "useDebugValue", Oe(), gy();
        },
        useDeferredValue: function(e) {
          return le = "useDeferredValue", Oe(), Wb(e);
        },
        useTransition: function() {
          return le = "useTransition", Oe(), qb();
        },
        useMutableSource: function(e, t, a) {
          return le = "useMutableSource", Oe(), void 0;
        },
        useSyncExternalStore: function(e, t, a) {
          return le = "useSyncExternalStore", Oe(), cy(e, t);
        },
        useId: function() {
          return le = "useId", Oe(), Cy();
        },
        unstable_isNewReconciler: Ie
      }, i1 = {
        readContext: function(e) {
          return Er(e);
        },
        useCallback: function(e, t) {
          return le = "useCallback", Oe(), Sy(e, t);
        },
        useContext: function(e) {
          return le = "useContext", Oe(), Er(e);
        },
        useEffect: function(e, t) {
          return le = "useEffect", Oe(), Sv(e, t);
        },
        useImperativeHandle: function(e, t, a) {
          return le = "useImperativeHandle", Oe(), yy(e, t, a);
        },
        useInsertionEffect: function(e, t) {
          return le = "useInsertionEffect", Oe(), hy(e, t);
        },
        useLayoutEffect: function(e, t) {
          return le = "useLayoutEffect", Oe(), my(e, t);
        },
        useMemo: function(e, t) {
          le = "useMemo", Oe();
          var a = Be.current;
          Be.current = Ty;
          try {
            return Ey(e, t);
          } finally {
            Be.current = a;
          }
        },
        useReducer: function(e, t, a) {
          le = "useReducer", Oe();
          var i = Be.current;
          Be.current = Ty;
          try {
            return lS(e, t, a);
          } finally {
            Be.current = i;
          }
        },
        useRef: function(e) {
          return le = "useRef", Oe(), dy();
        },
        useState: function(e) {
          le = "useState", Oe();
          var t = Be.current;
          Be.current = Ty;
          try {
            return cS(e);
          } finally {
            Be.current = t;
          }
        },
        useDebugValue: function(e, t) {
          return le = "useDebugValue", Oe(), gy();
        },
        useDeferredValue: function(e) {
          return le = "useDeferredValue", Oe(), Gb(e);
        },
        useTransition: function() {
          return le = "useTransition", Oe(), Kb();
        },
        useMutableSource: function(e, t, a) {
          return le = "useMutableSource", Oe(), void 0;
        },
        useSyncExternalStore: function(e, t, a) {
          return le = "useSyncExternalStore", Oe(), cy(e, t);
        },
        useId: function() {
          return le = "useId", Oe(), Cy();
        },
        unstable_isNewReconciler: Ie
      }, sl = {
        readContext: function(e) {
          return ES(), Er(e);
        },
        useCallback: function(e, t) {
          return le = "useCallback", gt(), Jt(), hS(e, t);
        },
        useContext: function(e) {
          return le = "useContext", gt(), Jt(), Er(e);
        },
        useEffect: function(e, t) {
          return le = "useEffect", gt(), Jt(), vy(e, t);
        },
        useImperativeHandle: function(e, t, a) {
          return le = "useImperativeHandle", gt(), Jt(), vS(e, t, a);
        },
        useInsertionEffect: function(e, t) {
          return le = "useInsertionEffect", gt(), Jt(), dS(e, t);
        },
        useLayoutEffect: function(e, t) {
          return le = "useLayoutEffect", gt(), Jt(), pS(e, t);
        },
        useMemo: function(e, t) {
          le = "useMemo", gt(), Jt();
          var a = Be.current;
          Be.current = sl;
          try {
            return mS(e, t);
          } finally {
            Be.current = a;
          }
        },
        useReducer: function(e, t, a) {
          le = "useReducer", gt(), Jt();
          var i = Be.current;
          Be.current = sl;
          try {
            return iS(e, t, a);
          } finally {
            Be.current = i;
          }
        },
        useRef: function(e) {
          return le = "useRef", gt(), Jt(), fS(e);
        },
        useState: function(e) {
          le = "useState", gt(), Jt();
          var t = Be.current;
          Be.current = sl;
          try {
            return fy(e);
          } finally {
            Be.current = t;
          }
        },
        useDebugValue: function(e, t) {
          return le = "useDebugValue", gt(), Jt(), void 0;
        },
        useDeferredValue: function(e) {
          return le = "useDeferredValue", gt(), Jt(), yS(e);
        },
        useTransition: function() {
          return le = "useTransition", gt(), Jt(), gS();
        },
        useMutableSource: function(e, t, a) {
          return le = "useMutableSource", gt(), Jt(), void 0;
        },
        useSyncExternalStore: function(e, t, a) {
          return le = "useSyncExternalStore", gt(), Jt(), uS(e, t, a);
        },
        useId: function() {
          return le = "useId", gt(), Jt(), SS();
        },
        unstable_isNewReconciler: Ie
      }, Ro = {
        readContext: function(e) {
          return ES(), Er(e);
        },
        useCallback: function(e, t) {
          return le = "useCallback", gt(), Oe(), Sy(e, t);
        },
        useContext: function(e) {
          return le = "useContext", gt(), Oe(), Er(e);
        },
        useEffect: function(e, t) {
          return le = "useEffect", gt(), Oe(), Sv(e, t);
        },
        useImperativeHandle: function(e, t, a) {
          return le = "useImperativeHandle", gt(), Oe(), yy(e, t, a);
        },
        useInsertionEffect: function(e, t) {
          return le = "useInsertionEffect", gt(), Oe(), hy(e, t);
        },
        useLayoutEffect: function(e, t) {
          return le = "useLayoutEffect", gt(), Oe(), my(e, t);
        },
        useMemo: function(e, t) {
          le = "useMemo", gt(), Oe();
          var a = Be.current;
          Be.current = Ro;
          try {
            return Ey(e, t);
          } finally {
            Be.current = a;
          }
        },
        useReducer: function(e, t, a) {
          le = "useReducer", gt(), Oe();
          var i = Be.current;
          Be.current = Ro;
          try {
            return oS(e, t, a);
          } finally {
            Be.current = i;
          }
        },
        useRef: function(e) {
          return le = "useRef", gt(), Oe(), dy();
        },
        useState: function(e) {
          le = "useState", gt(), Oe();
          var t = Be.current;
          Be.current = Ro;
          try {
            return sS(e);
          } finally {
            Be.current = t;
          }
        },
        useDebugValue: function(e, t) {
          return le = "useDebugValue", gt(), Oe(), gy();
        },
        useDeferredValue: function(e) {
          return le = "useDeferredValue", gt(), Oe(), Wb(e);
        },
        useTransition: function() {
          return le = "useTransition", gt(), Oe(), qb();
        },
        useMutableSource: function(e, t, a) {
          return le = "useMutableSource", gt(), Oe(), void 0;
        },
        useSyncExternalStore: function(e, t, a) {
          return le = "useSyncExternalStore", gt(), Oe(), cy(e, t);
        },
        useId: function() {
          return le = "useId", gt(), Oe(), Cy();
        },
        unstable_isNewReconciler: Ie
      }, Ty = {
        readContext: function(e) {
          return ES(), Er(e);
        },
        useCallback: function(e, t) {
          return le = "useCallback", gt(), Oe(), Sy(e, t);
        },
        useContext: function(e) {
          return le = "useContext", gt(), Oe(), Er(e);
        },
        useEffect: function(e, t) {
          return le = "useEffect", gt(), Oe(), Sv(e, t);
        },
        useImperativeHandle: function(e, t, a) {
          return le = "useImperativeHandle", gt(), Oe(), yy(e, t, a);
        },
        useInsertionEffect: function(e, t) {
          return le = "useInsertionEffect", gt(), Oe(), hy(e, t);
        },
        useLayoutEffect: function(e, t) {
          return le = "useLayoutEffect", gt(), Oe(), my(e, t);
        },
        useMemo: function(e, t) {
          le = "useMemo", gt(), Oe();
          var a = Be.current;
          Be.current = Ro;
          try {
            return Ey(e, t);
          } finally {
            Be.current = a;
          }
        },
        useReducer: function(e, t, a) {
          le = "useReducer", gt(), Oe();
          var i = Be.current;
          Be.current = Ro;
          try {
            return lS(e, t, a);
          } finally {
            Be.current = i;
          }
        },
        useRef: function(e) {
          return le = "useRef", gt(), Oe(), dy();
        },
        useState: function(e) {
          le = "useState", gt(), Oe();
          var t = Be.current;
          Be.current = Ro;
          try {
            return cS(e);
          } finally {
            Be.current = t;
          }
        },
        useDebugValue: function(e, t) {
          return le = "useDebugValue", gt(), Oe(), gy();
        },
        useDeferredValue: function(e) {
          return le = "useDeferredValue", gt(), Oe(), Gb(e);
        },
        useTransition: function() {
          return le = "useTransition", gt(), Oe(), Kb();
        },
        useMutableSource: function(e, t, a) {
          return le = "useMutableSource", gt(), Oe(), void 0;
        },
        useSyncExternalStore: function(e, t, a) {
          return le = "useSyncExternalStore", gt(), Oe(), cy(e, t);
        },
        useId: function() {
          return le = "useId", gt(), Oe(), Cy();
        },
        unstable_isNewReconciler: Ie
      };
    }
    var fs = v.unstable_now, o1 = 0, Ry = -1, Ev = -1, wy = -1, CS = !1, xy = !1;
    function l1() {
      return CS;
    }
    function Sk() {
      xy = !0;
    }
    function Ek() {
      CS = !1, xy = !1;
    }
    function Ck() {
      CS = xy, xy = !1;
    }
    function u1() {
      return o1;
    }
    function s1() {
      o1 = fs();
    }
    function bS(e) {
      Ev = fs(), e.actualStartTime < 0 && (e.actualStartTime = fs());
    }
    function c1(e) {
      Ev = -1;
    }
    function _y(e, t) {
      if (Ev >= 0) {
        var a = fs() - Ev;
        e.actualDuration += a, t && (e.selfBaseDuration = a), Ev = -1;
      }
    }
    function cl(e) {
      if (Ry >= 0) {
        var t = fs() - Ry;
        Ry = -1;
        for (var a = e.return; a !== null; ) {
          switch (a.tag) {
            case U:
              var i = a.stateNode;
              i.effectDuration += t;
              return;
            case q:
              var l = a.stateNode;
              l.effectDuration += t;
              return;
          }
          a = a.return;
        }
      }
    }
    function TS(e) {
      if (wy >= 0) {
        var t = fs() - wy;
        wy = -1;
        for (var a = e.return; a !== null; ) {
          switch (a.tag) {
            case U:
              var i = a.stateNode;
              i !== null && (i.passiveEffectDuration += t);
              return;
            case q:
              var l = a.stateNode;
              l !== null && (l.passiveEffectDuration += t);
              return;
          }
          a = a.return;
        }
      }
    }
    function fl() {
      Ry = fs();
    }
    function RS() {
      wy = fs();
    }
    function wS(e) {
      for (var t = e.child; t; )
        e.actualDuration += t.actualDuration, t = t.sibling;
    }
    function wo(e, t) {
      if (e && e.defaultProps) {
        var a = Et({}, t), i = e.defaultProps;
        for (var l in i)
          a[l] === void 0 && (a[l] = i[l]);
        return a;
      }
      return t;
    }
    var xS = {}, _S, kS, OS, DS, NS, f1, ky, AS, MS, LS, Cv;
    {
      _S = /* @__PURE__ */ new Set(), kS = /* @__PURE__ */ new Set(), OS = /* @__PURE__ */ new Set(), DS = /* @__PURE__ */ new Set(), AS = /* @__PURE__ */ new Set(), NS = /* @__PURE__ */ new Set(), MS = /* @__PURE__ */ new Set(), LS = /* @__PURE__ */ new Set(), Cv = /* @__PURE__ */ new Set();
      var d1 = /* @__PURE__ */ new Set();
      ky = function(e, t) {
        if (!(e === null || typeof e == "function")) {
          var a = t + "_" + e;
          d1.has(a) || (d1.add(a), g("%s(...): Expected the last optional `callback` argument to be a function. Instead received: %s.", t, e));
        }
      }, f1 = function(e, t) {
        if (t === void 0) {
          var a = $t(e) || "Component";
          NS.has(a) || (NS.add(a), g("%s.getDerivedStateFromProps(): A valid state object (or null) must be returned. You have returned undefined.", a));
        }
      }, Object.defineProperty(xS, "_processChildContext", {
        enumerable: !1,
        value: function() {
          throw new Error("_processChildContext is not available in React 16+. This likely means you have multiple copies of React and are attempting to nest a React 15 tree inside a React 16 tree using unstable_renderSubtreeIntoContainer, which isn't supported. Try to make sure you have only one copy of React (and ideally, switch to ReactDOM.createPortal).");
        }
      }), Object.freeze(xS);
    }
    function zS(e, t, a, i) {
      var l = e.memoizedState, c = a(i, l);
      {
        if (e.mode & Ct) {
          en(!0);
          try {
            c = a(i, l);
          } finally {
            en(!1);
          }
        }
        f1(t, c);
      }
      var p = c == null ? l : Et({}, l, c);
      if (e.memoizedState = p, e.lanes === oe) {
        var m = e.updateQueue;
        m.baseState = p;
      }
    }
    var US = {
      isMounted: ip,
      enqueueSetState: function(e, t, a) {
        var i = Lu(e), l = Ha(), c = hs(i), p = iu(l, c);
        p.payload = t, a != null && (ky(a, "setState"), p.callback = a);
        var m = ls(i, p, c);
        m !== null && (Ur(m, i, c, l), ry(m, i, c)), qs(i, c);
      },
      enqueueReplaceState: function(e, t, a) {
        var i = Lu(e), l = Ha(), c = hs(i), p = iu(l, c);
        p.tag = Ob, p.payload = t, a != null && (ky(a, "replaceState"), p.callback = a);
        var m = ls(i, p, c);
        m !== null && (Ur(m, i, c, l), ry(m, i, c)), qs(i, c);
      },
      enqueueForceUpdate: function(e, t) {
        var a = Lu(e), i = Ha(), l = hs(a), c = iu(i, l);
        c.tag = ey, t != null && (ky(t, "forceUpdate"), c.callback = t);
        var p = ls(a, c, l);
        p !== null && (Ur(p, a, l, i), ry(p, a, l)), Sp(a, l);
      }
    };
    function p1(e, t, a, i, l, c, p) {
      var m = e.stateNode;
      if (typeof m.shouldComponentUpdate == "function") {
        var E = m.shouldComponentUpdate(i, c, p);
        {
          if (e.mode & Ct) {
            en(!0);
            try {
              E = m.shouldComponentUpdate(i, c, p);
            } finally {
              en(!1);
            }
          }
          E === void 0 && g("%s.shouldComponentUpdate(): Returned undefined instead of a boolean value. Make sure to return true or false.", $t(t) || "Component");
        }
        return E;
      }
      return t.prototype && t.prototype.isPureReactComponent ? !at(a, i) || !at(l, c) : !0;
    }
    function bk(e, t, a) {
      var i = e.stateNode;
      {
        var l = $t(t) || "Component", c = i.render;
        c || (t.prototype && typeof t.prototype.render == "function" ? g("%s(...): No `render` method found on the returned component instance: did you accidentally return an object from the constructor?", l) : g("%s(...): No `render` method found on the returned component instance: you may have forgotten to define `render`.", l)), i.getInitialState && !i.getInitialState.isReactClassApproved && !i.state && g("getInitialState was defined on %s, a plain JavaScript class. This is only supported for classes created using React.createClass. Did you mean to define a state property instead?", l), i.getDefaultProps && !i.getDefaultProps.isReactClassApproved && g("getDefaultProps was defined on %s, a plain JavaScript class. This is only supported for classes created using React.createClass. Use a static property to define defaultProps instead.", l), i.propTypes && g("propTypes was defined as an instance property on %s. Use a static property to define propTypes instead.", l), i.contextType && g("contextType was defined as an instance property on %s. Use a static property to define contextType instead.", l), t.childContextTypes && !Cv.has(t) && // Strict Mode has its own warning for legacy context, so we can skip
        // this one.
        (e.mode & Ct) === rt && (Cv.add(t), g(`%s uses the legacy childContextTypes API which is no longer supported and will be removed in the next major release. Use React.createContext() instead

.Learn more about this warning here: https://reactjs.org/link/legacy-context`, l)), t.contextTypes && !Cv.has(t) && // Strict Mode has its own warning for legacy context, so we can skip
        // this one.
        (e.mode & Ct) === rt && (Cv.add(t), g(`%s uses the legacy contextTypes API which is no longer supported and will be removed in the next major release. Use React.createContext() with static contextType instead.

Learn more about this warning here: https://reactjs.org/link/legacy-context`, l)), i.contextTypes && g("contextTypes was defined as an instance property on %s. Use a static property to define contextTypes instead.", l), t.contextType && t.contextTypes && !MS.has(t) && (MS.add(t), g("%s declares both contextTypes and contextType static properties. The legacy contextTypes property will be ignored.", l)), typeof i.componentShouldUpdate == "function" && g("%s has a method called componentShouldUpdate(). Did you mean shouldComponentUpdate()? The name is phrased as a question because the function is expected to return a value.", l), t.prototype && t.prototype.isPureReactComponent && typeof i.shouldComponentUpdate < "u" && g("%s has a method called shouldComponentUpdate(). shouldComponentUpdate should not be used when extending React.PureComponent. Please extend React.Component if shouldComponentUpdate is used.", $t(t) || "A pure component"), typeof i.componentDidUnmount == "function" && g("%s has a method called componentDidUnmount(). But there is no such lifecycle method. Did you mean componentWillUnmount()?", l), typeof i.componentDidReceiveProps == "function" && g("%s has a method called componentDidReceiveProps(). But there is no such lifecycle method. If you meant to update the state in response to changing props, use componentWillReceiveProps(). If you meant to fetch data or run side-effects or mutations after React has updated the UI, use componentDidUpdate().", l), typeof i.componentWillRecieveProps == "function" && g("%s has a method called componentWillRecieveProps(). Did you mean componentWillReceiveProps()?", l), typeof i.UNSAFE_componentWillRecieveProps == "function" && g("%s has a method called UNSAFE_componentWillRecieveProps(). Did you mean UNSAFE_componentWillReceiveProps()?", l);
        var p = i.props !== a;
        i.props !== void 0 && p && g("%s(...): When calling super() in `%s`, make sure to pass up the same props that your component's constructor was passed.", l, l), i.defaultProps && g("Setting defaultProps as an instance property on %s is not supported and will be ignored. Instead, define defaultProps as a static property on %s.", l, l), typeof i.getSnapshotBeforeUpdate == "function" && typeof i.componentDidUpdate != "function" && !OS.has(t) && (OS.add(t), g("%s: getSnapshotBeforeUpdate() should be used with componentDidUpdate(). This component defines getSnapshotBeforeUpdate() only.", $t(t))), typeof i.getDerivedStateFromProps == "function" && g("%s: getDerivedStateFromProps() is defined as an instance method and will be ignored. Instead, declare it as a static method.", l), typeof i.getDerivedStateFromError == "function" && g("%s: getDerivedStateFromError() is defined as an instance method and will be ignored. Instead, declare it as a static method.", l), typeof t.getSnapshotBeforeUpdate == "function" && g("%s: getSnapshotBeforeUpdate() is defined as a static method and will be ignored. Instead, declare it as an instance method.", l);
        var m = i.state;
        m && (typeof m != "object" || bt(m)) && g("%s.state: must be set to an object or null", l), typeof i.getChildContext == "function" && typeof t.childContextTypes != "object" && g("%s.getChildContext(): childContextTypes must be defined in order to use getChildContext().", l);
      }
    }
    function v1(e, t) {
      t.updater = US, e.stateNode = t, Vs(t, e), t._reactInternalInstance = xS;
    }
    function h1(e, t, a) {
      var i = !1, l = Ri, c = Ri, p = t.contextType;
      if ("contextType" in t) {
        var m = (
          // Allow null for conditional declaration
          p === null || p !== void 0 && p.$$typeof === N && p._context === void 0
        );
        if (!m && !LS.has(t)) {
          LS.add(t);
          var E = "";
          p === void 0 ? E = " However, it is set to undefined. This can be caused by a typo or by mixing up named and default imports. This can also happen due to a circular dependency, so try moving the createContext() call to a separate file." : typeof p != "object" ? E = " However, it is set to a " + typeof p + "." : p.$$typeof === ro ? E = " Did you accidentally pass the Context.Provider instead?" : p._context !== void 0 ? E = " Did you accidentally pass the Context.Consumer instead?" : E = " However, it is set to an object with keys {" + Object.keys(p).join(", ") + "}.", g("%s defines an invalid contextType. contextType should point to the Context object returned by React.createContext().%s", $t(t) || "Component", E);
        }
      }
      if (typeof p == "object" && p !== null)
        c = Er(p);
      else {
        l = od(e, t, !0);
        var R = t.contextTypes;
        i = R != null, c = i ? ld(e, l) : Ri;
      }
      var w = new t(a, c);
      if (e.mode & Ct) {
        en(!0);
        try {
          w = new t(a, c);
        } finally {
          en(!1);
        }
      }
      var V = e.memoizedState = w.state !== null && w.state !== void 0 ? w.state : null;
      v1(e, w);
      {
        if (typeof t.getDerivedStateFromProps == "function" && V === null) {
          var $ = $t(t) || "Component";
          kS.has($) || (kS.add($), g("`%s` uses `getDerivedStateFromProps` but its initial state is %s. This is not recommended. Instead, define the initial state by assigning an object to `this.state` in the constructor of `%s`. This ensures that `getDerivedStateFromProps` arguments have a consistent shape.", $, w.state === null ? "null" : "undefined", $));
        }
        if (typeof t.getDerivedStateFromProps == "function" || typeof w.getSnapshotBeforeUpdate == "function") {
          var X = null, Z = null, ne = null;
          if (typeof w.componentWillMount == "function" && w.componentWillMount.__suppressDeprecationWarning !== !0 ? X = "componentWillMount" : typeof w.UNSAFE_componentWillMount == "function" && (X = "UNSAFE_componentWillMount"), typeof w.componentWillReceiveProps == "function" && w.componentWillReceiveProps.__suppressDeprecationWarning !== !0 ? Z = "componentWillReceiveProps" : typeof w.UNSAFE_componentWillReceiveProps == "function" && (Z = "UNSAFE_componentWillReceiveProps"), typeof w.componentWillUpdate == "function" && w.componentWillUpdate.__suppressDeprecationWarning !== !0 ? ne = "componentWillUpdate" : typeof w.UNSAFE_componentWillUpdate == "function" && (ne = "UNSAFE_componentWillUpdate"), X !== null || Z !== null || ne !== null) {
            var Me = $t(t) || "Component", lt = typeof t.getDerivedStateFromProps == "function" ? "getDerivedStateFromProps()" : "getSnapshotBeforeUpdate()";
            DS.has(Me) || (DS.add(Me), g(`Unsafe legacy lifecycles will not be called for components using new component APIs.

%s uses %s but also contains the following legacy lifecycles:%s%s%s

The above lifecycles should be removed. Learn more about this warning here:
https://reactjs.org/link/unsafe-component-lifecycles`, Me, lt, X !== null ? `
  ` + X : "", Z !== null ? `
  ` + Z : "", ne !== null ? `
  ` + ne : ""));
          }
        }
      }
      return i && ab(e, l, c), w;
    }
    function Tk(e, t) {
      var a = t.state;
      typeof t.componentWillMount == "function" && t.componentWillMount(), typeof t.UNSAFE_componentWillMount == "function" && t.UNSAFE_componentWillMount(), a !== t.state && (g("%s.componentWillMount(): Assigning directly to this.state is deprecated (except inside a component's constructor). Use setState instead.", ht(e) || "Component"), US.enqueueReplaceState(t, t.state, null));
    }
    function m1(e, t, a, i) {
      var l = t.state;
      if (typeof t.componentWillReceiveProps == "function" && t.componentWillReceiveProps(a, i), typeof t.UNSAFE_componentWillReceiveProps == "function" && t.UNSAFE_componentWillReceiveProps(a, i), t.state !== l) {
        {
          var c = ht(e) || "Component";
          _S.has(c) || (_S.add(c), g("%s.componentWillReceiveProps(): Assigning directly to this.state is deprecated (except inside a component's constructor). Use setState instead.", c));
        }
        US.enqueueReplaceState(t, t.state, null);
      }
    }
    function PS(e, t, a, i) {
      bk(e, t, a);
      var l = e.stateNode;
      l.props = a, l.state = e.memoizedState, l.refs = {}, W0(e);
      var c = t.contextType;
      if (typeof c == "object" && c !== null)
        l.context = Er(c);
      else {
        var p = od(e, t, !0);
        l.context = ld(e, p);
      }
      {
        if (l.state === a) {
          var m = $t(t) || "Component";
          AS.has(m) || (AS.add(m), g("%s: It is not recommended to assign props directly to state because updates to props won't be reflected in state. In most cases, it is better to use props directly.", m));
        }
        e.mode & Ct && bo.recordLegacyContextWarning(e, l), bo.recordUnsafeLifecycleWarnings(e, l);
      }
      l.state = e.memoizedState;
      var E = t.getDerivedStateFromProps;
      if (typeof E == "function" && (zS(e, t, E, a), l.state = e.memoizedState), typeof t.getDerivedStateFromProps != "function" && typeof l.getSnapshotBeforeUpdate != "function" && (typeof l.UNSAFE_componentWillMount == "function" || typeof l.componentWillMount == "function") && (Tk(e, l), ay(e, a, l, i), l.state = e.memoizedState), typeof l.componentDidMount == "function") {
        var R = At;
        R |= jo, (e.mode & cn) !== rt && (R |= Qr), e.flags |= R;
      }
    }
    function Rk(e, t, a, i) {
      var l = e.stateNode, c = e.memoizedProps;
      l.props = c;
      var p = l.context, m = t.contextType, E = Ri;
      if (typeof m == "object" && m !== null)
        E = Er(m);
      else {
        var R = od(e, t, !0);
        E = ld(e, R);
      }
      var w = t.getDerivedStateFromProps, V = typeof w == "function" || typeof l.getSnapshotBeforeUpdate == "function";
      !V && (typeof l.UNSAFE_componentWillReceiveProps == "function" || typeof l.componentWillReceiveProps == "function") && (c !== a || p !== E) && m1(e, l, a, E), Nb();
      var $ = e.memoizedState, X = l.state = $;
      if (ay(e, a, l, i), X = e.memoizedState, c === a && $ === X && !Fm() && !iy()) {
        if (typeof l.componentDidMount == "function") {
          var Z = At;
          Z |= jo, (e.mode & cn) !== rt && (Z |= Qr), e.flags |= Z;
        }
        return !1;
      }
      typeof w == "function" && (zS(e, t, w, a), X = e.memoizedState);
      var ne = iy() || p1(e, t, c, a, $, X, E);
      if (ne) {
        if (!V && (typeof l.UNSAFE_componentWillMount == "function" || typeof l.componentWillMount == "function") && (typeof l.componentWillMount == "function" && l.componentWillMount(), typeof l.UNSAFE_componentWillMount == "function" && l.UNSAFE_componentWillMount()), typeof l.componentDidMount == "function") {
          var Me = At;
          Me |= jo, (e.mode & cn) !== rt && (Me |= Qr), e.flags |= Me;
        }
      } else {
        if (typeof l.componentDidMount == "function") {
          var lt = At;
          lt |= jo, (e.mode & cn) !== rt && (lt |= Qr), e.flags |= lt;
        }
        e.memoizedProps = a, e.memoizedState = X;
      }
      return l.props = a, l.state = X, l.context = E, ne;
    }
    function wk(e, t, a, i, l) {
      var c = t.stateNode;
      Db(e, t);
      var p = t.memoizedProps, m = t.type === t.elementType ? p : wo(t.type, p);
      c.props = m;
      var E = t.pendingProps, R = c.context, w = a.contextType, V = Ri;
      if (typeof w == "object" && w !== null)
        V = Er(w);
      else {
        var $ = od(t, a, !0);
        V = ld(t, $);
      }
      var X = a.getDerivedStateFromProps, Z = typeof X == "function" || typeof c.getSnapshotBeforeUpdate == "function";
      !Z && (typeof c.UNSAFE_componentWillReceiveProps == "function" || typeof c.componentWillReceiveProps == "function") && (p !== E || R !== V) && m1(t, c, i, V), Nb();
      var ne = t.memoizedState, Me = c.state = ne;
      if (ay(t, i, c, l), Me = t.memoizedState, p === E && ne === Me && !Fm() && !iy())
        return typeof c.componentDidUpdate == "function" && (p !== e.memoizedProps || ne !== e.memoizedState) && (t.flags |= At), typeof c.getSnapshotBeforeUpdate == "function" && (p !== e.memoizedProps || ne !== e.memoizedState) && (t.flags |= Xa), !1;
      typeof X == "function" && (zS(t, a, X, i), Me = t.memoizedState);
      var lt = iy() || p1(t, a, m, i, ne, Me, V) || // TODO: In some cases, we'll end up checking if context has changed twice,
      // both before and after `shouldComponentUpdate` has been called. Not ideal,
      // but I'm loath to refactor this function. This only happens for memoized
      // components so it's not that common.
      ke;
      return lt ? (!Z && (typeof c.UNSAFE_componentWillUpdate == "function" || typeof c.componentWillUpdate == "function") && (typeof c.componentWillUpdate == "function" && c.componentWillUpdate(i, Me, V), typeof c.UNSAFE_componentWillUpdate == "function" && c.UNSAFE_componentWillUpdate(i, Me, V)), typeof c.componentDidUpdate == "function" && (t.flags |= At), typeof c.getSnapshotBeforeUpdate == "function" && (t.flags |= Xa)) : (typeof c.componentDidUpdate == "function" && (p !== e.memoizedProps || ne !== e.memoizedState) && (t.flags |= At), typeof c.getSnapshotBeforeUpdate == "function" && (p !== e.memoizedProps || ne !== e.memoizedState) && (t.flags |= Xa), t.memoizedProps = i, t.memoizedState = Me), c.props = i, c.state = Me, c.context = V, lt;
    }
    function Nc(e, t) {
      return {
        value: e,
        source: t,
        stack: Pt(t),
        digest: null
      };
    }
    function $S(e, t, a) {
      return {
        value: e,
        source: null,
        stack: a ?? null,
        digest: t ?? null
      };
    }
    function xk(e, t) {
      return !0;
    }
    function FS(e, t) {
      try {
        var a = xk(e, t);
        if (a === !1)
          return;
        var i = t.value, l = t.source, c = t.stack, p = c !== null ? c : "";
        if (i != null && i._suppressLogging) {
          if (e.tag === A)
            return;
          console.error(i);
        }
        var m = l ? ht(l) : null, E = m ? "The above error occurred in the <" + m + "> component:" : "The above error occurred in one of your React components:", R;
        if (e.tag === U)
          R = `Consider adding an error boundary to your tree to customize error handling behavior.
Visit https://reactjs.org/link/error-boundaries to learn more about error boundaries.`;
        else {
          var w = ht(e) || "Anonymous";
          R = "React will try to recreate this component tree from scratch " + ("using the error boundary you provided, " + w + ".");
        }
        var V = E + `
` + p + `

` + ("" + R);
        console.error(V);
      } catch ($) {
        setTimeout(function() {
          throw $;
        });
      }
    }
    var _k = typeof WeakMap == "function" ? WeakMap : Map;
    function y1(e, t, a) {
      var i = iu(tn, a);
      i.tag = I0, i.payload = {
        element: null
      };
      var l = t.value;
      return i.callback = function() {
        SD(l), FS(e, t);
      }, i;
    }
    function jS(e, t, a) {
      var i = iu(tn, a);
      i.tag = I0;
      var l = e.type.getDerivedStateFromError;
      if (typeof l == "function") {
        var c = t.value;
        i.payload = function() {
          return l(c);
        }, i.callback = function() {
          kT(e), FS(e, t);
        };
      }
      var p = e.stateNode;
      return p !== null && typeof p.componentDidCatch == "function" && (i.callback = function() {
        kT(e), FS(e, t), typeof l != "function" && yD(this);
        var E = t.value, R = t.stack;
        this.componentDidCatch(E, {
          componentStack: R !== null ? R : ""
        }), typeof l != "function" && (ga(e.lanes, ct) || g("%s: Error boundaries should implement getDerivedStateFromError(). In that method, return a state update to display an error message or fallback UI.", ht(e) || "Unknown"));
      }), i;
    }
    function g1(e, t, a) {
      var i = e.pingCache, l;
      if (i === null ? (i = e.pingCache = new _k(), l = /* @__PURE__ */ new Set(), i.set(t, l)) : (l = i.get(t), l === void 0 && (l = /* @__PURE__ */ new Set(), i.set(t, l))), !l.has(a)) {
        l.add(a);
        var c = ED.bind(null, e, t, a);
        Hr && $v(e, a), t.then(c, c);
      }
    }
    function kk(e, t, a, i) {
      var l = e.updateQueue;
      if (l === null) {
        var c = /* @__PURE__ */ new Set();
        c.add(a), e.updateQueue = c;
      } else
        l.add(a);
    }
    function Ok(e, t) {
      var a = e.tag;
      if ((e.mode & Dt) === rt && (a === z || a === ue || a === Ge)) {
        var i = e.alternate;
        i ? (e.updateQueue = i.updateQueue, e.memoizedState = i.memoizedState, e.lanes = i.lanes) : (e.updateQueue = null, e.memoizedState = null);
      }
    }
    function S1(e) {
      var t = e;
      do {
        if (t.tag === se && sk(t))
          return t;
        t = t.return;
      } while (t !== null);
      return null;
    }
    function E1(e, t, a, i, l) {
      if ((e.mode & Dt) === rt) {
        if (e === t)
          e.flags |= Ja;
        else {
          if (e.flags |= Ot, a.flags |= Si, a.flags &= -52805, a.tag === A) {
            var c = a.alternate;
            if (c === null)
              a.tag = x;
            else {
              var p = iu(tn, ct);
              p.tag = ey, ls(a, p, ct);
            }
          }
          a.lanes = Tt(a.lanes, ct);
        }
        return e;
      }
      return e.flags |= Ja, e.lanes = l, e;
    }
    function Dk(e, t, a, i, l) {
      if (a.flags |= Ll, Hr && $v(e, l), i !== null && typeof i == "object" && typeof i.then == "function") {
        var c = i;
        Ok(a), Jr() && a.mode & Dt && fb();
        var p = S1(t);
        if (p !== null) {
          p.flags &= -257, E1(p, t, a, e, l), p.mode & Dt && g1(e, c, l), kk(p, e, c);
          return;
        } else {
          if (!bp(l)) {
            g1(e, c, l), SE();
            return;
          }
          var m = new Error("A component suspended while responding to synchronous input. This will cause the UI to be replaced with a loading indicator. To fix, updates that suspend should be wrapped with startTransition.");
          i = m;
        }
      } else if (Jr() && a.mode & Dt) {
        fb();
        var E = S1(t);
        if (E !== null) {
          (E.flags & Ja) === nt && (E.flags |= Un), E1(E, t, a, e, l), A0(Nc(i, a));
          return;
        }
      }
      i = Nc(i, a), sD(i);
      var R = t;
      do {
        switch (R.tag) {
          case U: {
            var w = i;
            R.flags |= Ja;
            var V = gr(l);
            R.lanes = Tt(R.lanes, V);
            var $ = y1(R, w, V);
            G0(R, $);
            return;
          }
          case A:
            var X = i, Z = R.type, ne = R.stateNode;
            if ((R.flags & Ot) === nt && (typeof Z.getDerivedStateFromError == "function" || ne !== null && typeof ne.componentDidCatch == "function" && !ST(ne))) {
              R.flags |= Ja;
              var Me = gr(l);
              R.lanes = Tt(R.lanes, Me);
              var lt = jS(R, X, Me);
              G0(R, lt);
              return;
            }
            break;
        }
        R = R.return;
      } while (R !== null);
    }
    function Nk() {
      return null;
    }
    var bv = y.ReactCurrentOwner, xo = !1, HS, Tv, VS, BS, IS, Ac, YS, Oy, Rv;
    HS = {}, Tv = {}, VS = {}, BS = {}, IS = {}, Ac = !1, YS = {}, Oy = {}, Rv = {};
    function Fa(e, t, a, i) {
      e === null ? t.child = Tb(t, null, a, i) : t.child = fd(t, e.child, a, i);
    }
    function Ak(e, t, a, i) {
      t.child = fd(t, e.child, null, i), t.child = fd(t, null, a, i);
    }
    function C1(e, t, a, i, l) {
      if (t.type !== t.elementType) {
        var c = a.propTypes;
        c && Eo(
          c,
          i,
          // Resolved props
          "prop",
          $t(a)
        );
      }
      var p = a.render, m = t.ref, E, R;
      pd(t, l), Za(t);
      {
        if (bv.current = t, Wa(!0), E = Sd(e, t, p, i, m, l), R = Ed(), t.mode & Ct) {
          en(!0);
          try {
            E = Sd(e, t, p, i, m, l), R = Ed();
          } finally {
            en(!1);
          }
        }
        Wa(!1);
      }
      return Yo(), e !== null && !xo ? (Pb(e, t, l), ou(e, t, l)) : (Jr() && R && x0(t), t.flags |= ho, Fa(e, t, E, l), t.child);
    }
    function b1(e, t, a, i, l) {
      if (e === null) {
        var c = a.type;
        if (PD(c) && a.compare === null && // SimpleMemoComponent codepath doesn't resolve outer props either.
        a.defaultProps === void 0) {
          var p = c;
          return p = kd(c), t.tag = Ge, t.type = p, QS(t, c), T1(e, t, p, i, l);
        }
        {
          var m = c.propTypes;
          if (m && Eo(
            m,
            i,
            // Resolved props
            "prop",
            $t(c)
          ), a.defaultProps !== void 0) {
            var E = $t(c) || "Unknown";
            Rv[E] || (g("%s: Support for defaultProps will be removed from memo components in a future major release. Use JavaScript default parameters instead.", E), Rv[E] = !0);
          }
        }
        var R = DE(a.type, null, i, t, t.mode, l);
        return R.ref = t.ref, R.return = t, t.child = R, R;
      }
      {
        var w = a.type, V = w.propTypes;
        V && Eo(
          V,
          i,
          // Resolved props
          "prop",
          $t(w)
        );
      }
      var $ = e.child, X = eE(e, l);
      if (!X) {
        var Z = $.memoizedProps, ne = a.compare;
        if (ne = ne !== null ? ne : at, ne(Z, i) && e.ref === t.ref)
          return ou(e, t, l);
      }
      t.flags |= ho;
      var Me = Pc($, i);
      return Me.ref = t.ref, Me.return = t, t.child = Me, Me;
    }
    function T1(e, t, a, i, l) {
      if (t.type !== t.elementType) {
        var c = t.elementType;
        if (c.$$typeof === yt) {
          var p = c, m = p._payload, E = p._init;
          try {
            c = E(m);
          } catch {
            c = null;
          }
          var R = c && c.propTypes;
          R && Eo(
            R,
            i,
            // Resolved (SimpleMemoComponent has no defaultProps)
            "prop",
            $t(c)
          );
        }
      }
      if (e !== null) {
        var w = e.memoizedProps;
        if (at(w, i) && e.ref === t.ref && // Prevent bailout if the implementation changed due to hot reload.
        t.type === e.type)
          if (xo = !1, t.pendingProps = i = w, eE(e, l))
            (e.flags & Si) !== nt && (xo = !0);
          else return t.lanes = e.lanes, ou(e, t, l);
      }
      return WS(e, t, a, i, l);
    }
    function R1(e, t, a) {
      var i = t.pendingProps, l = i.children, c = e !== null ? e.memoizedState : null;
      if (i.mode === "hidden" || k)
        if ((t.mode & Dt) === rt) {
          var p = {
            baseLanes: oe,
            cachePool: null,
            transitions: null
          };
          t.memoizedState = p, Vy(t, a);
        } else if (ga(a, La)) {
          var V = {
            baseLanes: oe,
            cachePool: null,
            transitions: null
          };
          t.memoizedState = V;
          var $ = c !== null ? c.baseLanes : a;
          Vy(t, $);
        } else {
          var m = null, E;
          if (c !== null) {
            var R = c.baseLanes;
            E = Tt(R, a);
          } else
            E = a;
          t.lanes = t.childLanes = La;
          var w = {
            baseLanes: E,
            cachePool: m,
            transitions: null
          };
          return t.memoizedState = w, t.updateQueue = null, Vy(t, E), null;
        }
      else {
        var X;
        c !== null ? (X = Tt(c.baseLanes, a), t.memoizedState = null) : X = a, Vy(t, X);
      }
      return Fa(e, t, l, a), t.child;
    }
    function Mk(e, t, a) {
      var i = t.pendingProps;
      return Fa(e, t, i, a), t.child;
    }
    function Lk(e, t, a) {
      var i = t.pendingProps.children;
      return Fa(e, t, i, a), t.child;
    }
    function zk(e, t, a) {
      {
        t.flags |= At;
        {
          var i = t.stateNode;
          i.effectDuration = 0, i.passiveEffectDuration = 0;
        }
      }
      var l = t.pendingProps, c = l.children;
      return Fa(e, t, c, a), t.child;
    }
    function w1(e, t) {
      var a = t.ref;
      (e === null && a !== null || e !== null && e.ref !== a) && (t.flags |= Xn, t.flags |= Is);
    }
    function WS(e, t, a, i, l) {
      if (t.type !== t.elementType) {
        var c = a.propTypes;
        c && Eo(
          c,
          i,
          // Resolved props
          "prop",
          $t(a)
        );
      }
      var p;
      {
        var m = od(t, a, !0);
        p = ld(t, m);
      }
      var E, R;
      pd(t, l), Za(t);
      {
        if (bv.current = t, Wa(!0), E = Sd(e, t, a, i, p, l), R = Ed(), t.mode & Ct) {
          en(!0);
          try {
            E = Sd(e, t, a, i, p, l), R = Ed();
          } finally {
            en(!1);
          }
        }
        Wa(!1);
      }
      return Yo(), e !== null && !xo ? (Pb(e, t, l), ou(e, t, l)) : (Jr() && R && x0(t), t.flags |= ho, Fa(e, t, E, l), t.child);
    }
    function x1(e, t, a, i, l) {
      {
        switch (JD(t)) {
          case !1: {
            var c = t.stateNode, p = t.type, m = new p(t.memoizedProps, c.context), E = m.state;
            c.updater.enqueueSetState(c, E, null);
            break;
          }
          case !0: {
            t.flags |= Ot, t.flags |= Ja;
            var R = new Error("Simulated error coming from DevTools"), w = gr(l);
            t.lanes = Tt(t.lanes, w);
            var V = jS(t, Nc(R, t), w);
            G0(t, V);
            break;
          }
        }
        if (t.type !== t.elementType) {
          var $ = a.propTypes;
          $ && Eo(
            $,
            i,
            // Resolved props
            "prop",
            $t(a)
          );
        }
      }
      var X;
      ol(a) ? (X = !0, Hm(t)) : X = !1, pd(t, l);
      var Z = t.stateNode, ne;
      Z === null ? (Ny(e, t), h1(t, a, i), PS(t, a, i, l), ne = !0) : e === null ? ne = Rk(t, a, i, l) : ne = wk(e, t, a, i, l);
      var Me = GS(e, t, a, ne, X, l);
      {
        var lt = t.stateNode;
        ne && lt.props !== i && (Ac || g("It looks like %s is reassigning its own `this.props` while rendering. This is not supported and can lead to confusing bugs.", ht(t) || "a component"), Ac = !0);
      }
      return Me;
    }
    function GS(e, t, a, i, l, c) {
      w1(e, t);
      var p = (t.flags & Ot) !== nt;
      if (!i && !p)
        return l && lb(t, a, !1), ou(e, t, c);
      var m = t.stateNode;
      bv.current = t;
      var E;
      if (p && typeof a.getDerivedStateFromError != "function")
        E = null, c1();
      else {
        Za(t);
        {
          if (Wa(!0), E = m.render(), t.mode & Ct) {
            en(!0);
            try {
              m.render();
            } finally {
              en(!1);
            }
          }
          Wa(!1);
        }
        Yo();
      }
      return t.flags |= ho, e !== null && p ? Ak(e, t, E, c) : Fa(e, t, E, c), t.memoizedState = m.state, l && lb(t, a, !0), t.child;
    }
    function _1(e) {
      var t = e.stateNode;
      t.pendingContext ? ib(e, t.pendingContext, t.pendingContext !== t.context) : t.context && ib(e, t.context, !1), Q0(e, t.containerInfo);
    }
    function Uk(e, t, a) {
      if (_1(t), e === null)
        throw new Error("Should have a current fiber. This is a bug in React.");
      var i = t.pendingProps, l = t.memoizedState, c = l.element;
      Db(e, t), ay(t, i, null, a);
      var p = t.memoizedState;
      t.stateNode;
      var m = p.element;
      if (l.isDehydrated) {
        var E = {
          element: m,
          isDehydrated: !1,
          cache: p.cache,
          pendingSuspenseBoundaries: p.pendingSuspenseBoundaries,
          transitions: p.transitions
        }, R = t.updateQueue;
        if (R.baseState = E, t.memoizedState = E, t.flags & Un) {
          var w = Nc(new Error("There was an error while hydrating. Because the error happened outside of a Suspense boundary, the entire root will switch to client rendering."), t);
          return k1(e, t, m, a, w);
        } else if (m !== c) {
          var V = Nc(new Error("This root received an early update, before anything was able hydrate. Switched the entire root to client rendering."), t);
          return k1(e, t, m, a, V);
        } else {
          F_(t);
          var $ = Tb(t, null, m, a);
          t.child = $;
          for (var X = $; X; )
            X.flags = X.flags & -3 | Jn, X = X.sibling;
        }
      } else {
        if (cd(), m === c)
          return ou(e, t, a);
        Fa(e, t, m, a);
      }
      return t.child;
    }
    function k1(e, t, a, i, l) {
      return cd(), A0(l), t.flags |= Un, Fa(e, t, a, i), t.child;
    }
    function Pk(e, t, a) {
      Lb(t), e === null && N0(t);
      var i = t.type, l = t.pendingProps, c = e !== null ? e.memoizedProps : null, p = l.children, m = d0(i, l);
      return m ? p = null : c !== null && d0(i, c) && (t.flags |= sn), w1(e, t), Fa(e, t, p, a), t.child;
    }
    function $k(e, t) {
      return e === null && N0(t), null;
    }
    function Fk(e, t, a, i) {
      Ny(e, t);
      var l = t.pendingProps, c = a, p = c._payload, m = c._init, E = m(p);
      t.type = E;
      var R = t.tag = $D(E), w = wo(E, l), V;
      switch (R) {
        case z:
          return QS(t, E), t.type = E = kd(E), V = WS(null, t, E, w, i), V;
        case A:
          return t.type = E = RE(E), V = x1(null, t, E, w, i), V;
        case ue:
          return t.type = E = wE(E), V = C1(null, t, E, w, i), V;
        case Ce: {
          if (t.type !== t.elementType) {
            var $ = E.propTypes;
            $ && Eo(
              $,
              w,
              // Resolved for outer only
              "prop",
              $t(E)
            );
          }
          return V = b1(
            null,
            t,
            E,
            wo(E.type, w),
            // The inner type can have defaults too
            i
          ), V;
        }
      }
      var X = "";
      throw E !== null && typeof E == "object" && E.$$typeof === yt && (X = " Did you wrap a component in React.lazy() more than once?"), new Error("Element type is invalid. Received a promise that resolves to: " + E + ". " + ("Lazy element type must resolve to a class or function." + X));
    }
    function jk(e, t, a, i, l) {
      Ny(e, t), t.tag = A;
      var c;
      return ol(a) ? (c = !0, Hm(t)) : c = !1, pd(t, l), h1(t, a, i), PS(t, a, i, l), GS(null, t, a, !0, c, l);
    }
    function Hk(e, t, a, i) {
      Ny(e, t);
      var l = t.pendingProps, c;
      {
        var p = od(t, a, !1);
        c = ld(t, p);
      }
      pd(t, i);
      var m, E;
      Za(t);
      {
        if (a.prototype && typeof a.prototype.render == "function") {
          var R = $t(a) || "Unknown";
          HS[R] || (g("The <%s /> component appears to have a render method, but doesn't extend React.Component. This is likely to cause errors. Change %s to extend React.Component instead.", R, R), HS[R] = !0);
        }
        t.mode & Ct && bo.recordLegacyContextWarning(t, null), Wa(!0), bv.current = t, m = Sd(null, t, a, l, c, i), E = Ed(), Wa(!1);
      }
      if (Yo(), t.flags |= ho, typeof m == "object" && m !== null && typeof m.render == "function" && m.$$typeof === void 0) {
        var w = $t(a) || "Unknown";
        Tv[w] || (g("The <%s /> component appears to be a function component that returns a class instance. Change %s to a class that extends React.Component instead. If you can't use a class try assigning the prototype on the function as a workaround. `%s.prototype = React.Component.prototype`. Don't use an arrow function since it cannot be called with `new` by React.", w, w, w), Tv[w] = !0);
      }
      if (
        // Run these checks in production only if the flag is off.
        // Eventually we'll delete this branch altogether.
        typeof m == "object" && m !== null && typeof m.render == "function" && m.$$typeof === void 0
      ) {
        {
          var V = $t(a) || "Unknown";
          Tv[V] || (g("The <%s /> component appears to be a function component that returns a class instance. Change %s to a class that extends React.Component instead. If you can't use a class try assigning the prototype on the function as a workaround. `%s.prototype = React.Component.prototype`. Don't use an arrow function since it cannot be called with `new` by React.", V, V, V), Tv[V] = !0);
        }
        t.tag = A, t.memoizedState = null, t.updateQueue = null;
        var $ = !1;
        return ol(a) ? ($ = !0, Hm(t)) : $ = !1, t.memoizedState = m.state !== null && m.state !== void 0 ? m.state : null, W0(t), v1(t, m), PS(t, a, l, i), GS(null, t, a, !0, $, i);
      } else {
        if (t.tag = z, t.mode & Ct) {
          en(!0);
          try {
            m = Sd(null, t, a, l, c, i), E = Ed();
          } finally {
            en(!1);
          }
        }
        return Jr() && E && x0(t), Fa(null, t, m, i), QS(t, a), t.child;
      }
    }
    function QS(e, t) {
      {
        if (t && t.childContextTypes && g("%s(...): childContextTypes cannot be defined on a function component.", t.displayName || t.name || "Component"), e.ref !== null) {
          var a = "", i = Wr();
          i && (a += `

Check the render method of \`` + i + "`.");
          var l = i || "", c = e._debugSource;
          c && (l = c.fileName + ":" + c.lineNumber), IS[l] || (IS[l] = !0, g("Function components cannot be given refs. Attempts to access this ref will fail. Did you mean to use React.forwardRef()?%s", a));
        }
        if (t.defaultProps !== void 0) {
          var p = $t(t) || "Unknown";
          Rv[p] || (g("%s: Support for defaultProps will be removed from function components in a future major release. Use JavaScript default parameters instead.", p), Rv[p] = !0);
        }
        if (typeof t.getDerivedStateFromProps == "function") {
          var m = $t(t) || "Unknown";
          BS[m] || (g("%s: Function components do not support getDerivedStateFromProps.", m), BS[m] = !0);
        }
        if (typeof t.contextType == "object" && t.contextType !== null) {
          var E = $t(t) || "Unknown";
          VS[E] || (g("%s: Function components do not support contextType.", E), VS[E] = !0);
        }
      }
    }
    var qS = {
      dehydrated: null,
      treeContext: null,
      retryLane: er
    };
    function KS(e) {
      return {
        baseLanes: e,
        cachePool: Nk(),
        transitions: null
      };
    }
    function Vk(e, t) {
      var a = null;
      return {
        baseLanes: Tt(e.baseLanes, t),
        cachePool: a,
        transitions: e.transitions
      };
    }
    function Bk(e, t, a, i) {
      if (t !== null) {
        var l = t.memoizedState;
        if (l === null)
          return !1;
      }
      return X0(e, pv);
    }
    function Ik(e, t) {
      return ac(e.childLanes, t);
    }
    function O1(e, t, a) {
      var i = t.pendingProps;
      ZD(t) && (t.flags |= Ot);
      var l = To.current, c = !1, p = (t.flags & Ot) !== nt;
      if (p || Bk(l, e) ? (c = !0, t.flags &= -129) : (e === null || e.memoizedState !== null) && (l = uk(l, Ub)), l = hd(l), ss(t, l), e === null) {
        N0(t);
        var m = t.memoizedState;
        if (m !== null) {
          var E = m.dehydrated;
          if (E !== null)
            return qk(t, E);
        }
        var R = i.children, w = i.fallback;
        if (c) {
          var V = Yk(t, R, w, a), $ = t.child;
          return $.memoizedState = KS(a), t.memoizedState = qS, V;
        } else
          return XS(t, R);
      } else {
        var X = e.memoizedState;
        if (X !== null) {
          var Z = X.dehydrated;
          if (Z !== null)
            return Kk(e, t, p, i, Z, X, a);
        }
        if (c) {
          var ne = i.fallback, Me = i.children, lt = Gk(e, t, Me, ne, a), tt = t.child, jt = e.child.memoizedState;
          return tt.memoizedState = jt === null ? KS(a) : Vk(jt, a), tt.childLanes = Ik(e, a), t.memoizedState = qS, lt;
        } else {
          var Lt = i.children, W = Wk(e, t, Lt, a);
          return t.memoizedState = null, W;
        }
      }
    }
    function XS(e, t, a) {
      var i = e.mode, l = {
        mode: "visible",
        children: t
      }, c = JS(l, i);
      return c.return = e, e.child = c, c;
    }
    function Yk(e, t, a, i) {
      var l = e.mode, c = e.child, p = {
        mode: "hidden",
        children: t
      }, m, E;
      return (l & Dt) === rt && c !== null ? (m = c, m.childLanes = oe, m.pendingProps = p, e.mode & zt && (m.actualDuration = 0, m.actualStartTime = -1, m.selfBaseDuration = 0, m.treeBaseDuration = 0), E = ys(a, l, i, null)) : (m = JS(p, l), E = ys(a, l, i, null)), m.return = e, E.return = e, m.sibling = E, e.child = m, E;
    }
    function JS(e, t, a) {
      return DT(e, t, oe, null);
    }
    function D1(e, t) {
      return Pc(e, t);
    }
    function Wk(e, t, a, i) {
      var l = e.child, c = l.sibling, p = D1(l, {
        mode: "visible",
        children: a
      });
      if ((t.mode & Dt) === rt && (p.lanes = i), p.return = t, p.sibling = null, c !== null) {
        var m = t.deletions;
        m === null ? (t.deletions = [c], t.flags |= pa) : m.push(c);
      }
      return t.child = p, p;
    }
    function Gk(e, t, a, i, l) {
      var c = t.mode, p = e.child, m = p.sibling, E = {
        mode: "hidden",
        children: a
      }, R;
      if (
        // In legacy mode, we commit the primary tree as if it successfully
        // completed, even though it's in an inconsistent state.
        (c & Dt) === rt && // Make sure we're on the second pass, i.e. the primary child fragment was
        // already cloned. In legacy mode, the only case where this isn't true is
        // when DevTools forces us to display a fallback; we skip the first render
        // pass entirely and go straight to rendering the fallback. (In Concurrent
        // Mode, SuspenseList can also trigger this scenario, but this is a legacy-
        // only codepath.)
        t.child !== p
      ) {
        var w = t.child;
        R = w, R.childLanes = oe, R.pendingProps = E, t.mode & zt && (R.actualDuration = 0, R.actualStartTime = -1, R.selfBaseDuration = p.selfBaseDuration, R.treeBaseDuration = p.treeBaseDuration), t.deletions = null;
      } else
        R = D1(p, E), R.subtreeFlags = p.subtreeFlags & Zn;
      var V;
      return m !== null ? V = Pc(m, i) : (V = ys(i, c, l, null), V.flags |= Kn), V.return = t, R.return = t, R.sibling = V, t.child = R, V;
    }
    function Dy(e, t, a, i) {
      i !== null && A0(i), fd(t, e.child, null, a);
      var l = t.pendingProps, c = l.children, p = XS(t, c);
      return p.flags |= Kn, t.memoizedState = null, p;
    }
    function Qk(e, t, a, i, l) {
      var c = t.mode, p = {
        mode: "visible",
        children: a
      }, m = JS(p, c), E = ys(i, c, l, null);
      return E.flags |= Kn, m.return = t, E.return = t, m.sibling = E, t.child = m, (t.mode & Dt) !== rt && fd(t, e.child, null, l), E;
    }
    function qk(e, t, a) {
      return (e.mode & Dt) === rt ? (g("Cannot hydrate Suspense in legacy mode. Switch from ReactDOM.hydrate(element, container) to ReactDOMClient.hydrateRoot(container, <App />).render(element) or remove the Suspense components from the server rendered components."), e.lanes = ct) : m0(t) ? e.lanes = yr : e.lanes = La, null;
    }
    function Kk(e, t, a, i, l, c, p) {
      if (a)
        if (t.flags & Un) {
          t.flags &= -257;
          var W = $S(new Error("There was an error while hydrating this Suspense boundary. Switched to client rendering."));
          return Dy(e, t, p, W);
        } else {
          if (t.memoizedState !== null)
            return t.child = e.child, t.flags |= Ot, null;
          var re = i.children, G = i.fallback, me = Qk(e, t, re, G, p), We = t.child;
          return We.memoizedState = KS(p), t.memoizedState = qS, me;
        }
      else {
        if (P_(), (t.mode & Dt) === rt)
          return Dy(
            e,
            t,
            p,
            // TODO: When we delete legacy mode, we should make this error argument
            // required — every concurrent mode path that causes hydration to
            // de-opt to client rendering should have an error message.
            null
          );
        if (m0(l)) {
          var m, E, R;
          {
            var w = e_(l);
            m = w.digest, E = w.message, R = w.stack;
          }
          var V;
          E ? V = new Error(E) : V = new Error("The server could not finish this Suspense boundary, likely due to an error during server rendering. Switched to client rendering.");
          var $ = $S(V, m, R);
          return Dy(e, t, p, $);
        }
        var X = ga(p, e.childLanes);
        if (xo || X) {
          var Z = Hy();
          if (Z !== null) {
            var ne = zf(Z, p);
            if (ne !== er && ne !== c.retryLane) {
              c.retryLane = ne;
              var Me = tn;
              ii(e, ne), Ur(Z, e, ne, Me);
            }
          }
          SE();
          var lt = $S(new Error("This Suspense boundary received an update before it finished hydrating. This caused the boundary to switch to client rendering. The usual way to fix this is to wrap the original update in startTransition."));
          return Dy(e, t, p, lt);
        } else if (ZC(l)) {
          t.flags |= Ot, t.child = e.child;
          var tt = CD.bind(null, e);
          return t_(l, tt), null;
        } else {
          j_(t, l, c.treeContext);
          var jt = i.children, Lt = XS(t, jt);
          return Lt.flags |= Jn, Lt;
        }
      }
    }
    function N1(e, t, a) {
      e.lanes = Tt(e.lanes, t);
      var i = e.alternate;
      i !== null && (i.lanes = Tt(i.lanes, t)), V0(e.return, t, a);
    }
    function Xk(e, t, a) {
      for (var i = t; i !== null; ) {
        if (i.tag === se) {
          var l = i.memoizedState;
          l !== null && N1(i, a, e);
        } else if (i.tag === je)
          N1(i, a, e);
        else if (i.child !== null) {
          i.child.return = i, i = i.child;
          continue;
        }
        if (i === e)
          return;
        for (; i.sibling === null; ) {
          if (i.return === null || i.return === e)
            return;
          i = i.return;
        }
        i.sibling.return = i.return, i = i.sibling;
      }
    }
    function Jk(e) {
      for (var t = e, a = null; t !== null; ) {
        var i = t.alternate;
        i !== null && uy(i) === null && (a = t), t = t.sibling;
      }
      return a;
    }
    function Zk(e) {
      if (e !== void 0 && e !== "forwards" && e !== "backwards" && e !== "together" && !YS[e])
        if (YS[e] = !0, typeof e == "string")
          switch (e.toLowerCase()) {
            case "together":
            case "forwards":
            case "backwards": {
              g('"%s" is not a valid value for revealOrder on <SuspenseList />. Use lowercase "%s" instead.', e, e.toLowerCase());
              break;
            }
            case "forward":
            case "backward": {
              g('"%s" is not a valid value for revealOrder on <SuspenseList />. React uses the -s suffix in the spelling. Use "%ss" instead.', e, e.toLowerCase());
              break;
            }
            default:
              g('"%s" is not a supported revealOrder on <SuspenseList />. Did you mean "together", "forwards" or "backwards"?', e);
              break;
          }
        else
          g('%s is not a supported value for revealOrder on <SuspenseList />. Did you mean "together", "forwards" or "backwards"?', e);
    }
    function eO(e, t) {
      e !== void 0 && !Oy[e] && (e !== "collapsed" && e !== "hidden" ? (Oy[e] = !0, g('"%s" is not a supported value for tail on <SuspenseList />. Did you mean "collapsed" or "hidden"?', e)) : t !== "forwards" && t !== "backwards" && (Oy[e] = !0, g('<SuspenseList tail="%s" /> is only valid if revealOrder is "forwards" or "backwards". Did you mean to specify revealOrder="forwards"?', e)));
    }
    function A1(e, t) {
      {
        var a = bt(e), i = !a && typeof Dn(e) == "function";
        if (a || i) {
          var l = a ? "array" : "iterable";
          return g("A nested %s was passed to row #%s in <SuspenseList />. Wrap it in an additional SuspenseList to configure its revealOrder: <SuspenseList revealOrder=...> ... <SuspenseList revealOrder=...>{%s}</SuspenseList> ... </SuspenseList>", l, t, l), !1;
        }
      }
      return !0;
    }
    function tO(e, t) {
      if ((t === "forwards" || t === "backwards") && e !== void 0 && e !== null && e !== !1)
        if (bt(e)) {
          for (var a = 0; a < e.length; a++)
            if (!A1(e[a], a))
              return;
        } else {
          var i = Dn(e);
          if (typeof i == "function") {
            var l = i.call(e);
            if (l)
              for (var c = l.next(), p = 0; !c.done; c = l.next()) {
                if (!A1(c.value, p))
                  return;
                p++;
              }
          } else
            g('A single row was passed to a <SuspenseList revealOrder="%s" />. This is not useful since it needs multiple rows. Did you mean to pass multiple children or an array?', t);
        }
    }
    function ZS(e, t, a, i, l) {
      var c = e.memoizedState;
      c === null ? e.memoizedState = {
        isBackwards: t,
        rendering: null,
        renderingStartTime: 0,
        last: i,
        tail: a,
        tailMode: l
      } : (c.isBackwards = t, c.rendering = null, c.renderingStartTime = 0, c.last = i, c.tail = a, c.tailMode = l);
    }
    function M1(e, t, a) {
      var i = t.pendingProps, l = i.revealOrder, c = i.tail, p = i.children;
      Zk(l), eO(c, l), tO(p, l), Fa(e, t, p, a);
      var m = To.current, E = X0(m, pv);
      if (E)
        m = J0(m, pv), t.flags |= Ot;
      else {
        var R = e !== null && (e.flags & Ot) !== nt;
        R && Xk(t, t.child, a), m = hd(m);
      }
      if (ss(t, m), (t.mode & Dt) === rt)
        t.memoizedState = null;
      else
        switch (l) {
          case "forwards": {
            var w = Jk(t.child), V;
            w === null ? (V = t.child, t.child = null) : (V = w.sibling, w.sibling = null), ZS(
              t,
              !1,
              // isBackwards
              V,
              w,
              c
            );
            break;
          }
          case "backwards": {
            var $ = null, X = t.child;
            for (t.child = null; X !== null; ) {
              var Z = X.alternate;
              if (Z !== null && uy(Z) === null) {
                t.child = X;
                break;
              }
              var ne = X.sibling;
              X.sibling = $, $ = X, X = ne;
            }
            ZS(
              t,
              !0,
              // isBackwards
              $,
              null,
              // last
              c
            );
            break;
          }
          case "together": {
            ZS(
              t,
              !1,
              // isBackwards
              null,
              // tail
              null,
              // last
              void 0
            );
            break;
          }
          default:
            t.memoizedState = null;
        }
      return t.child;
    }
    function nO(e, t, a) {
      Q0(t, t.stateNode.containerInfo);
      var i = t.pendingProps;
      return e === null ? t.child = fd(t, null, i, a) : Fa(e, t, i, a), t.child;
    }
    var L1 = !1;
    function rO(e, t, a) {
      var i = t.type, l = i._context, c = t.pendingProps, p = t.memoizedProps, m = c.value;
      {
        "value" in c || L1 || (L1 = !0, g("The `value` prop is required for the `<Context.Provider>`. Did you misspell it or forget to pass it?"));
        var E = t.type.propTypes;
        E && Eo(E, c, "prop", "Context.Provider");
      }
      if (xb(t, l, m), p !== null) {
        var R = p.value;
        if ($e(R, m)) {
          if (p.children === c.children && !Fm())
            return ou(e, t, a);
        } else
          Z_(t, l, a);
      }
      var w = c.children;
      return Fa(e, t, w, a), t.child;
    }
    var z1 = !1;
    function aO(e, t, a) {
      var i = t.type;
      i._context === void 0 ? i !== i.Consumer && (z1 || (z1 = !0, g("Rendering <Context> directly is not supported and will be removed in a future major release. Did you mean to render <Context.Consumer> instead?"))) : i = i._context;
      var l = t.pendingProps, c = l.children;
      typeof c != "function" && g("A context consumer was rendered with multiple children, or a child that isn't a function. A context consumer expects a single child that is a function. If you did pass a function, make sure there is no trailing or leading whitespace around it."), pd(t, a);
      var p = Er(i);
      Za(t);
      var m;
      return bv.current = t, Wa(!0), m = c(p), Wa(!1), Yo(), t.flags |= ho, Fa(e, t, m, a), t.child;
    }
    function wv() {
      xo = !0;
    }
    function Ny(e, t) {
      (t.mode & Dt) === rt && e !== null && (e.alternate = null, t.alternate = null, t.flags |= Kn);
    }
    function ou(e, t, a) {
      return e !== null && (t.dependencies = e.dependencies), c1(), Pv(t.lanes), ga(a, t.childLanes) ? (X_(e, t), t.child) : null;
    }
    function iO(e, t, a) {
      {
        var i = t.return;
        if (i === null)
          throw new Error("Cannot swap the root fiber.");
        if (e.alternate = null, t.alternate = null, a.index = t.index, a.sibling = t.sibling, a.return = t.return, a.ref = t.ref, t === i.child)
          i.child = a;
        else {
          var l = i.child;
          if (l === null)
            throw new Error("Expected parent to have a child.");
          for (; l.sibling !== t; )
            if (l = l.sibling, l === null)
              throw new Error("Expected to find the previous sibling.");
          l.sibling = a;
        }
        var c = i.deletions;
        return c === null ? (i.deletions = [e], i.flags |= pa) : c.push(e), a.flags |= Kn, a;
      }
    }
    function eE(e, t) {
      var a = e.lanes;
      return !!ga(a, t);
    }
    function oO(e, t, a) {
      switch (t.tag) {
        case U:
          _1(t), t.stateNode, cd();
          break;
        case B:
          Lb(t);
          break;
        case A: {
          var i = t.type;
          ol(i) && Hm(t);
          break;
        }
        case te:
          Q0(t, t.stateNode.containerInfo);
          break;
        case de: {
          var l = t.memoizedProps.value, c = t.type._context;
          xb(t, c, l);
          break;
        }
        case q:
          {
            var p = ga(a, t.childLanes);
            p && (t.flags |= At);
            {
              var m = t.stateNode;
              m.effectDuration = 0, m.passiveEffectDuration = 0;
            }
          }
          break;
        case se: {
          var E = t.memoizedState;
          if (E !== null) {
            if (E.dehydrated !== null)
              return ss(t, hd(To.current)), t.flags |= Ot, null;
            var R = t.child, w = R.childLanes;
            if (ga(a, w))
              return O1(e, t, a);
            ss(t, hd(To.current));
            var V = ou(e, t, a);
            return V !== null ? V.sibling : null;
          } else
            ss(t, hd(To.current));
          break;
        }
        case je: {
          var $ = (e.flags & Ot) !== nt, X = ga(a, t.childLanes);
          if ($) {
            if (X)
              return M1(e, t, a);
            t.flags |= Ot;
          }
          var Z = t.memoizedState;
          if (Z !== null && (Z.rendering = null, Z.tail = null, Z.lastEffect = null), ss(t, To.current), X)
            break;
          return null;
        }
        case Pe:
        case pt:
          return t.lanes = oe, R1(e, t, a);
      }
      return ou(e, t, a);
    }
    function U1(e, t, a) {
      if (t._debugNeedsRemount && e !== null)
        return iO(e, t, DE(t.type, t.key, t.pendingProps, t._debugOwner || null, t.mode, t.lanes));
      if (e !== null) {
        var i = e.memoizedProps, l = t.pendingProps;
        if (i !== l || Fm() || // Force a re-render if the implementation changed due to hot reload:
        t.type !== e.type)
          xo = !0;
        else {
          var c = eE(e, a);
          if (!c && // If this is the second pass of an error or suspense boundary, there
          // may not be work scheduled on `current`, so we check for this flag.
          (t.flags & Ot) === nt)
            return xo = !1, oO(e, t, a);
          (e.flags & Si) !== nt ? xo = !0 : xo = !1;
        }
      } else if (xo = !1, Jr() && N_(t)) {
        var p = t.index, m = A_();
        cb(t, m, p);
      }
      switch (t.lanes = oe, t.tag) {
        case F:
          return Hk(e, t, t.type, a);
        case _t: {
          var E = t.elementType;
          return Fk(e, t, E, a);
        }
        case z: {
          var R = t.type, w = t.pendingProps, V = t.elementType === R ? w : wo(R, w);
          return WS(e, t, R, V, a);
        }
        case A: {
          var $ = t.type, X = t.pendingProps, Z = t.elementType === $ ? X : wo($, X);
          return x1(e, t, $, Z, a);
        }
        case U:
          return Uk(e, t, a);
        case B:
          return Pk(e, t, a);
        case M:
          return $k(e, t);
        case se:
          return O1(e, t, a);
        case te:
          return nO(e, t, a);
        case ue: {
          var ne = t.type, Me = t.pendingProps, lt = t.elementType === ne ? Me : wo(ne, Me);
          return C1(e, t, ne, lt, a);
        }
        case j:
          return Mk(e, t, a);
        case ce:
          return Lk(e, t, a);
        case q:
          return zk(e, t, a);
        case de:
          return rO(e, t, a);
        case De:
          return aO(e, t, a);
        case Ce: {
          var tt = t.type, jt = t.pendingProps, Lt = wo(tt, jt);
          if (t.type !== t.elementType) {
            var W = tt.propTypes;
            W && Eo(
              W,
              Lt,
              // Resolved for outer only
              "prop",
              $t(tt)
            );
          }
          return Lt = wo(tt.type, Lt), b1(e, t, tt, Lt, a);
        }
        case Ge:
          return T1(e, t, t.type, t.pendingProps, a);
        case x: {
          var re = t.type, G = t.pendingProps, me = t.elementType === re ? G : wo(re, G);
          return jk(e, t, re, me, a);
        }
        case je:
          return M1(e, t, a);
        case Qe:
          break;
        case Pe:
          return R1(e, t, a);
      }
      throw new Error("Unknown unit of work tag (" + t.tag + "). This error is likely caused by a bug in React. Please file an issue.");
    }
    function Cd(e) {
      e.flags |= At;
    }
    function P1(e) {
      e.flags |= Xn, e.flags |= Is;
    }
    var $1, tE, F1, j1;
    $1 = function(e, t, a, i) {
      for (var l = t.child; l !== null; ) {
        if (l.tag === B || l.tag === M)
          kx(e, l.stateNode);
        else if (l.tag !== te) {
          if (l.child !== null) {
            l.child.return = l, l = l.child;
            continue;
          }
        }
        if (l === t)
          return;
        for (; l.sibling === null; ) {
          if (l.return === null || l.return === t)
            return;
          l = l.return;
        }
        l.sibling.return = l.return, l = l.sibling;
      }
    }, tE = function(e, t) {
    }, F1 = function(e, t, a, i, l) {
      var c = e.memoizedProps;
      if (c !== i) {
        var p = t.stateNode, m = q0(), E = Dx(p, a, c, i, l, m);
        t.updateQueue = E, E && Cd(t);
      }
    }, j1 = function(e, t, a, i) {
      a !== i && Cd(t);
    };
    function xv(e, t) {
      if (!Jr())
        switch (e.tailMode) {
          case "hidden": {
            for (var a = e.tail, i = null; a !== null; )
              a.alternate !== null && (i = a), a = a.sibling;
            i === null ? e.tail = null : i.sibling = null;
            break;
          }
          case "collapsed": {
            for (var l = e.tail, c = null; l !== null; )
              l.alternate !== null && (c = l), l = l.sibling;
            c === null ? !t && e.tail !== null ? e.tail.sibling = null : e.tail = null : c.sibling = null;
            break;
          }
        }
    }
    function ea(e) {
      var t = e.alternate !== null && e.alternate.child === e.child, a = oe, i = nt;
      if (t) {
        if ((e.mode & zt) !== rt) {
          for (var E = e.selfBaseDuration, R = e.child; R !== null; )
            a = Tt(a, Tt(R.lanes, R.childLanes)), i |= R.subtreeFlags & Zn, i |= R.flags & Zn, E += R.treeBaseDuration, R = R.sibling;
          e.treeBaseDuration = E;
        } else
          for (var w = e.child; w !== null; )
            a = Tt(a, Tt(w.lanes, w.childLanes)), i |= w.subtreeFlags & Zn, i |= w.flags & Zn, w.return = e, w = w.sibling;
        e.subtreeFlags |= i;
      } else {
        if ((e.mode & zt) !== rt) {
          for (var l = e.actualDuration, c = e.selfBaseDuration, p = e.child; p !== null; )
            a = Tt(a, Tt(p.lanes, p.childLanes)), i |= p.subtreeFlags, i |= p.flags, l += p.actualDuration, c += p.treeBaseDuration, p = p.sibling;
          e.actualDuration = l, e.treeBaseDuration = c;
        } else
          for (var m = e.child; m !== null; )
            a = Tt(a, Tt(m.lanes, m.childLanes)), i |= m.subtreeFlags, i |= m.flags, m.return = e, m = m.sibling;
        e.subtreeFlags |= i;
      }
      return e.childLanes = a, t;
    }
    function lO(e, t, a) {
      if (Y_() && (t.mode & Dt) !== rt && (t.flags & Ot) === nt)
        return yb(t), cd(), t.flags |= Un | Ll | Ja, !1;
      var i = Wm(t);
      if (a !== null && a.dehydrated !== null)
        if (e === null) {
          if (!i)
            throw new Error("A dehydrated suspense component was completed without a hydrated node. This is probably a bug in React.");
          if (B_(t), ea(t), (t.mode & zt) !== rt) {
            var l = a !== null;
            if (l) {
              var c = t.child;
              c !== null && (t.treeBaseDuration -= c.treeBaseDuration);
            }
          }
          return !1;
        } else {
          if (cd(), (t.flags & Ot) === nt && (t.memoizedState = null), t.flags |= At, ea(t), (t.mode & zt) !== rt) {
            var p = a !== null;
            if (p) {
              var m = t.child;
              m !== null && (t.treeBaseDuration -= m.treeBaseDuration);
            }
          }
          return !1;
        }
      else
        return gb(), !0;
    }
    function H1(e, t, a) {
      var i = t.pendingProps;
      switch (_0(t), t.tag) {
        case F:
        case _t:
        case Ge:
        case z:
        case ue:
        case j:
        case ce:
        case q:
        case De:
        case Ce:
          return ea(t), null;
        case A: {
          var l = t.type;
          return ol(l) && jm(t), ea(t), null;
        }
        case U: {
          var c = t.stateNode;
          if (vd(t), T0(t), eS(), c.pendingContext && (c.context = c.pendingContext, c.pendingContext = null), e === null || e.child === null) {
            var p = Wm(t);
            if (p)
              Cd(t);
            else if (e !== null) {
              var m = e.memoizedState;
              // Check if this is a client root
              (!m.isDehydrated || // Check if we reverted to client rendering (e.g. due to an error)
              (t.flags & Un) !== nt) && (t.flags |= Xa, gb());
            }
          }
          return tE(e, t), ea(t), null;
        }
        case B: {
          K0(t);
          var E = Mb(), R = t.type;
          if (e !== null && t.stateNode != null)
            F1(e, t, R, i, E), e.ref !== t.ref && P1(t);
          else {
            if (!i) {
              if (t.stateNode === null)
                throw new Error("We must have new props for new mounts. This error is likely caused by a bug in React. Please file an issue.");
              return ea(t), null;
            }
            var w = q0(), V = Wm(t);
            if (V)
              H_(t, E, w) && Cd(t);
            else {
              var $ = _x(R, i, E, w, t);
              $1($, t, !1, !1), t.stateNode = $, Ox($, R, i, E) && Cd(t);
            }
            t.ref !== null && P1(t);
          }
          return ea(t), null;
        }
        case M: {
          var X = i;
          if (e && t.stateNode != null) {
            var Z = e.memoizedProps;
            j1(e, t, Z, X);
          } else {
            if (typeof X != "string" && t.stateNode === null)
              throw new Error("We must have new props for new mounts. This error is likely caused by a bug in React. Please file an issue.");
            var ne = Mb(), Me = q0(), lt = Wm(t);
            lt ? V_(t) && Cd(t) : t.stateNode = Nx(X, ne, Me, t);
          }
          return ea(t), null;
        }
        case se: {
          md(t);
          var tt = t.memoizedState;
          if (e === null || e.memoizedState !== null && e.memoizedState.dehydrated !== null) {
            var jt = lO(e, t, tt);
            if (!jt)
              return t.flags & Ja ? t : null;
          }
          if ((t.flags & Ot) !== nt)
            return t.lanes = a, (t.mode & zt) !== rt && wS(t), t;
          var Lt = tt !== null, W = e !== null && e.memoizedState !== null;
          if (Lt !== W && Lt) {
            var re = t.child;
            if (re.flags |= Fi, (t.mode & Dt) !== rt) {
              var G = e === null && (t.memoizedProps.unstable_avoidThisFallback !== !0 || !0);
              G || X0(To.current, Ub) ? uD() : SE();
            }
          }
          var me = t.updateQueue;
          if (me !== null && (t.flags |= At), ea(t), (t.mode & zt) !== rt && Lt) {
            var We = t.child;
            We !== null && (t.treeBaseDuration -= We.treeBaseDuration);
          }
          return null;
        }
        case te:
          return vd(t), tE(e, t), e === null && R_(t.stateNode.containerInfo), ea(t), null;
        case de:
          var Fe = t.type._context;
          return H0(Fe, t), ea(t), null;
        case x: {
          var dt = t.type;
          return ol(dt) && jm(t), ea(t), null;
        }
        case je: {
          md(t);
          var St = t.memoizedState;
          if (St === null)
            return ea(t), null;
          var dn = (t.flags & Ot) !== nt, It = St.rendering;
          if (It === null)
            if (dn)
              xv(St, !1);
            else {
              var cr = cD() && (e === null || (e.flags & Ot) === nt);
              if (!cr)
                for (var Yt = t.child; Yt !== null; ) {
                  var nr = uy(Yt);
                  if (nr !== null) {
                    dn = !0, t.flags |= Ot, xv(St, !1);
                    var Ra = nr.updateQueue;
                    return Ra !== null && (t.updateQueue = Ra, t.flags |= At), t.subtreeFlags = nt, J_(t, a), ss(t, J0(To.current, pv)), t.child;
                  }
                  Yt = Yt.sibling;
                }
              St.tail !== null && Vn() > uT() && (t.flags |= Ot, dn = !0, xv(St, !1), t.lanes = Ih);
            }
          else {
            if (!dn) {
              var ia = uy(It);
              if (ia !== null) {
                t.flags |= Ot, dn = !0;
                var xi = ia.updateQueue;
                if (xi !== null && (t.updateQueue = xi, t.flags |= At), xv(St, !0), St.tail === null && St.tailMode === "hidden" && !It.alternate && !Jr())
                  return ea(t), null;
              } else // The time it took to render last row is greater than the remaining
              // time we have to render. So rendering one more row would likely
              // exceed it.
              Vn() * 2 - St.renderingStartTime > uT() && a !== La && (t.flags |= Ot, dn = !0, xv(St, !1), t.lanes = Ih);
            }
            if (St.isBackwards)
              It.sibling = t.child, t.child = It;
            else {
              var Va = St.last;
              Va !== null ? Va.sibling = It : t.child = It, St.last = It;
            }
          }
          if (St.tail !== null) {
            var Ba = St.tail;
            St.rendering = Ba, St.tail = Ba.sibling, St.renderingStartTime = Vn(), Ba.sibling = null;
            var wa = To.current;
            return dn ? wa = J0(wa, pv) : wa = hd(wa), ss(t, wa), Ba;
          }
          return ea(t), null;
        }
        case Qe:
          break;
        case Pe:
        case pt: {
          gE(t);
          var fu = t.memoizedState, Od = fu !== null;
          if (e !== null) {
            var Vv = e.memoizedState, vl = Vv !== null;
            vl !== Od && (t.flags |= Fi);
          }
          return !Od || (t.mode & Dt) === rt ? ea(t) : ga(pl, La) && (ea(t), t.subtreeFlags & (Kn | At) && (t.flags |= Fi)), null;
        }
        case vt:
          return null;
        case ot:
          return null;
      }
      throw new Error("Unknown unit of work tag (" + t.tag + "). This error is likely caused by a bug in React. Please file an issue.");
    }
    function uO(e, t, a) {
      switch (_0(t), t.tag) {
        case A: {
          var i = t.type;
          ol(i) && jm(t);
          var l = t.flags;
          return l & Ja ? (t.flags = l & -65537 | Ot, (t.mode & zt) !== rt && wS(t), t) : null;
        }
        case U: {
          t.stateNode, vd(t), T0(t), eS();
          var c = t.flags;
          return (c & Ja) !== nt && (c & Ot) === nt ? (t.flags = c & -65537 | Ot, t) : null;
        }
        case B:
          return K0(t), null;
        case se: {
          md(t);
          var p = t.memoizedState;
          if (p !== null && p.dehydrated !== null) {
            if (t.alternate === null)
              throw new Error("Threw in newly mounted dehydrated component. This is likely a bug in React. Please file an issue.");
            cd();
          }
          var m = t.flags;
          return m & Ja ? (t.flags = m & -65537 | Ot, (t.mode & zt) !== rt && wS(t), t) : null;
        }
        case je:
          return md(t), null;
        case te:
          return vd(t), null;
        case de:
          var E = t.type._context;
          return H0(E, t), null;
        case Pe:
        case pt:
          return gE(t), null;
        case vt:
          return null;
        default:
          return null;
      }
    }
    function V1(e, t, a) {
      switch (_0(t), t.tag) {
        case A: {
          var i = t.type.childContextTypes;
          i != null && jm(t);
          break;
        }
        case U: {
          t.stateNode, vd(t), T0(t), eS();
          break;
        }
        case B: {
          K0(t);
          break;
        }
        case te:
          vd(t);
          break;
        case se:
          md(t);
          break;
        case je:
          md(t);
          break;
        case de:
          var l = t.type._context;
          H0(l, t);
          break;
        case Pe:
        case pt:
          gE(t);
          break;
      }
    }
    var B1 = null;
    B1 = /* @__PURE__ */ new Set();
    var Ay = !1, ta = !1, sO = typeof WeakSet == "function" ? WeakSet : Set, Je = null, bd = null, Td = null;
    function cO(e) {
      Ka(null, function() {
        throw e;
      }), rp();
    }
    var fO = function(e, t) {
      if (t.props = e.memoizedProps, t.state = e.memoizedState, e.mode & zt)
        try {
          fl(), t.componentWillUnmount();
        } finally {
          cl(e);
        }
      else
        t.componentWillUnmount();
    };
    function I1(e, t) {
      try {
        ds(Dr, e);
      } catch (a) {
        _n(e, t, a);
      }
    }
    function nE(e, t, a) {
      try {
        fO(e, a);
      } catch (i) {
        _n(e, t, i);
      }
    }
    function dO(e, t, a) {
      try {
        a.componentDidMount();
      } catch (i) {
        _n(e, t, i);
      }
    }
    function Y1(e, t) {
      try {
        G1(e);
      } catch (a) {
        _n(e, t, a);
      }
    }
    function Rd(e, t) {
      var a = e.ref;
      if (a !== null)
        if (typeof a == "function") {
          var i;
          try {
            if (be && Le && e.mode & zt)
              try {
                fl(), i = a(null);
              } finally {
                cl(e);
              }
            else
              i = a(null);
          } catch (l) {
            _n(e, t, l);
          }
          typeof i == "function" && g("Unexpected return value from a callback ref in %s. A callback ref should not return a function.", ht(e));
        } else
          a.current = null;
    }
    function My(e, t, a) {
      try {
        a();
      } catch (i) {
        _n(e, t, i);
      }
    }
    var W1 = !1;
    function pO(e, t) {
      wx(e.containerInfo), Je = t, vO();
      var a = W1;
      return W1 = !1, a;
    }
    function vO() {
      for (; Je !== null; ) {
        var e = Je, t = e.child;
        (e.subtreeFlags & Vo) !== nt && t !== null ? (t.return = e, Je = t) : hO();
      }
    }
    function hO() {
      for (; Je !== null; ) {
        var e = Je;
        on(e);
        try {
          mO(e);
        } catch (a) {
          _n(e, e.return, a);
        }
        zn();
        var t = e.sibling;
        if (t !== null) {
          t.return = e.return, Je = t;
          return;
        }
        Je = e.return;
      }
    }
    function mO(e) {
      var t = e.alternate, a = e.flags;
      if ((a & Xa) !== nt) {
        switch (on(e), e.tag) {
          case z:
          case ue:
          case Ge:
            break;
          case A: {
            if (t !== null) {
              var i = t.memoizedProps, l = t.memoizedState, c = e.stateNode;
              e.type === e.elementType && !Ac && (c.props !== e.memoizedProps && g("Expected %s props to match memoized props before getSnapshotBeforeUpdate. This might either be because of a bug in React, or because a component reassigns its own `this.props`. Please file an issue.", ht(e) || "instance"), c.state !== e.memoizedState && g("Expected %s state to match memoized state before getSnapshotBeforeUpdate. This might either be because of a bug in React, or because a component reassigns its own `this.state`. Please file an issue.", ht(e) || "instance"));
              var p = c.getSnapshotBeforeUpdate(e.elementType === e.type ? i : wo(e.type, i), l);
              {
                var m = B1;
                p === void 0 && !m.has(e.type) && (m.add(e.type), g("%s.getSnapshotBeforeUpdate(): A snapshot value (or null) must be returned. You have returned undefined.", ht(e)));
              }
              c.__reactInternalSnapshotBeforeUpdate = p;
            }
            break;
          }
          case U: {
            {
              var E = e.stateNode;
              Kx(E.containerInfo);
            }
            break;
          }
          case B:
          case M:
          case te:
          case x:
            break;
          default:
            throw new Error("This unit of work tag should not have side-effects. This error is likely caused by a bug in React. Please file an issue.");
        }
        zn();
      }
    }
    function _o(e, t, a) {
      var i = t.updateQueue, l = i !== null ? i.lastEffect : null;
      if (l !== null) {
        var c = l.next, p = c;
        do {
          if ((p.tag & e) === e) {
            var m = p.destroy;
            p.destroy = void 0, m !== void 0 && ((e & Zr) !== oi ? Wo(t) : (e & Dr) !== oi && hp(t), (e & ll) !== oi && Fv(!0), My(t, a, m), (e & ll) !== oi && Fv(!1), (e & Zr) !== oi ? uf() : (e & Dr) !== oi && $u());
          }
          p = p.next;
        } while (p !== c);
      }
    }
    function ds(e, t) {
      var a = t.updateQueue, i = a !== null ? a.lastEffect : null;
      if (i !== null) {
        var l = i.next, c = l;
        do {
          if ((c.tag & e) === e) {
            (e & Zr) !== oi ? Vh(t) : (e & Dr) !== oi && Bh(t);
            var p = c.create;
            (e & ll) !== oi && Fv(!0), c.destroy = p(), (e & ll) !== oi && Fv(!1), (e & Zr) !== oi ? yo() : (e & Dr) !== oi && sf();
            {
              var m = c.destroy;
              if (m !== void 0 && typeof m != "function") {
                var E = void 0;
                (c.tag & Dr) !== nt ? E = "useLayoutEffect" : (c.tag & ll) !== nt ? E = "useInsertionEffect" : E = "useEffect";
                var R = void 0;
                m === null ? R = " You returned null. If your effect does not require clean up, return undefined (or nothing)." : typeof m.then == "function" ? R = `

It looks like you wrote ` + E + `(async () => ...) or returned a Promise. Instead, write the async function inside your effect and call it immediately:

` + E + `(() => {
  async function fetchData() {
    // You can await here
    const response = await MyAPI.getData(someId);
    // ...
  }
  fetchData();
}, [someId]); // Or [] if effect doesn't need props or state

Learn more about data fetching with Hooks: https://reactjs.org/link/hooks-data-fetching` : R = " You returned: " + m, g("%s must not return anything besides a function, which is used for clean-up.%s", E, R);
              }
            }
          }
          c = c.next;
        } while (c !== l);
      }
    }
    function yO(e, t) {
      if ((t.flags & At) !== nt)
        switch (t.tag) {
          case q: {
            var a = t.stateNode.passiveEffectDuration, i = t.memoizedProps, l = i.id, c = i.onPostCommit, p = u1(), m = t.alternate === null ? "mount" : "update";
            l1() && (m = "nested-update"), typeof c == "function" && c(l, m, a, p);
            var E = t.return;
            e: for (; E !== null; ) {
              switch (E.tag) {
                case U:
                  var R = E.stateNode;
                  R.passiveEffectDuration += a;
                  break e;
                case q:
                  var w = E.stateNode;
                  w.passiveEffectDuration += a;
                  break e;
              }
              E = E.return;
            }
            break;
          }
        }
    }
    function gO(e, t, a, i) {
      if ((a.flags & Bo) !== nt)
        switch (a.tag) {
          case z:
          case ue:
          case Ge: {
            if (!ta)
              if (a.mode & zt)
                try {
                  fl(), ds(Dr | Or, a);
                } finally {
                  cl(a);
                }
              else
                ds(Dr | Or, a);
            break;
          }
          case A: {
            var l = a.stateNode;
            if (a.flags & At && !ta)
              if (t === null)
                if (a.type === a.elementType && !Ac && (l.props !== a.memoizedProps && g("Expected %s props to match memoized props before componentDidMount. This might either be because of a bug in React, or because a component reassigns its own `this.props`. Please file an issue.", ht(a) || "instance"), l.state !== a.memoizedState && g("Expected %s state to match memoized state before componentDidMount. This might either be because of a bug in React, or because a component reassigns its own `this.state`. Please file an issue.", ht(a) || "instance")), a.mode & zt)
                  try {
                    fl(), l.componentDidMount();
                  } finally {
                    cl(a);
                  }
                else
                  l.componentDidMount();
              else {
                var c = a.elementType === a.type ? t.memoizedProps : wo(a.type, t.memoizedProps), p = t.memoizedState;
                if (a.type === a.elementType && !Ac && (l.props !== a.memoizedProps && g("Expected %s props to match memoized props before componentDidUpdate. This might either be because of a bug in React, or because a component reassigns its own `this.props`. Please file an issue.", ht(a) || "instance"), l.state !== a.memoizedState && g("Expected %s state to match memoized state before componentDidUpdate. This might either be because of a bug in React, or because a component reassigns its own `this.state`. Please file an issue.", ht(a) || "instance")), a.mode & zt)
                  try {
                    fl(), l.componentDidUpdate(c, p, l.__reactInternalSnapshotBeforeUpdate);
                  } finally {
                    cl(a);
                  }
                else
                  l.componentDidUpdate(c, p, l.__reactInternalSnapshotBeforeUpdate);
              }
            var m = a.updateQueue;
            m !== null && (a.type === a.elementType && !Ac && (l.props !== a.memoizedProps && g("Expected %s props to match memoized props before processing the update queue. This might either be because of a bug in React, or because a component reassigns its own `this.props`. Please file an issue.", ht(a) || "instance"), l.state !== a.memoizedState && g("Expected %s state to match memoized state before processing the update queue. This might either be because of a bug in React, or because a component reassigns its own `this.state`. Please file an issue.", ht(a) || "instance")), Ab(a, m, l));
            break;
          }
          case U: {
            var E = a.updateQueue;
            if (E !== null) {
              var R = null;
              if (a.child !== null)
                switch (a.child.tag) {
                  case B:
                    R = a.child.stateNode;
                    break;
                  case A:
                    R = a.child.stateNode;
                    break;
                }
              Ab(a, E, R);
            }
            break;
          }
          case B: {
            var w = a.stateNode;
            if (t === null && a.flags & At) {
              var V = a.type, $ = a.memoizedProps;
              Ux(w, V, $);
            }
            break;
          }
          case M:
            break;
          case te:
            break;
          case q: {
            {
              var X = a.memoizedProps, Z = X.onCommit, ne = X.onRender, Me = a.stateNode.effectDuration, lt = u1(), tt = t === null ? "mount" : "update";
              l1() && (tt = "nested-update"), typeof ne == "function" && ne(a.memoizedProps.id, tt, a.actualDuration, a.treeBaseDuration, a.actualStartTime, lt);
              {
                typeof Z == "function" && Z(a.memoizedProps.id, tt, Me, lt), hD(a);
                var jt = a.return;
                e: for (; jt !== null; ) {
                  switch (jt.tag) {
                    case U:
                      var Lt = jt.stateNode;
                      Lt.effectDuration += Me;
                      break e;
                    case q:
                      var W = jt.stateNode;
                      W.effectDuration += Me;
                      break e;
                  }
                  jt = jt.return;
                }
              }
            }
            break;
          }
          case se: {
            xO(e, a);
            break;
          }
          case je:
          case x:
          case Qe:
          case Pe:
          case pt:
          case ot:
            break;
          default:
            throw new Error("This unit of work tag should not have side-effects. This error is likely caused by a bug in React. Please file an issue.");
        }
      ta || a.flags & Xn && G1(a);
    }
    function SO(e) {
      switch (e.tag) {
        case z:
        case ue:
        case Ge: {
          if (e.mode & zt)
            try {
              fl(), I1(e, e.return);
            } finally {
              cl(e);
            }
          else
            I1(e, e.return);
          break;
        }
        case A: {
          var t = e.stateNode;
          typeof t.componentDidMount == "function" && dO(e, e.return, t), Y1(e, e.return);
          break;
        }
        case B: {
          Y1(e, e.return);
          break;
        }
      }
    }
    function EO(e, t) {
      for (var a = null, i = e; ; ) {
        if (i.tag === B) {
          if (a === null) {
            a = i;
            try {
              var l = i.stateNode;
              t ? Wx(l) : Qx(i.stateNode, i.memoizedProps);
            } catch (p) {
              _n(e, e.return, p);
            }
          }
        } else if (i.tag === M) {
          if (a === null)
            try {
              var c = i.stateNode;
              t ? Gx(c) : qx(c, i.memoizedProps);
            } catch (p) {
              _n(e, e.return, p);
            }
        } else if (!((i.tag === Pe || i.tag === pt) && i.memoizedState !== null && i !== e)) {
          if (i.child !== null) {
            i.child.return = i, i = i.child;
            continue;
          }
        }
        if (i === e)
          return;
        for (; i.sibling === null; ) {
          if (i.return === null || i.return === e)
            return;
          a === i && (a = null), i = i.return;
        }
        a === i && (a = null), i.sibling.return = i.return, i = i.sibling;
      }
    }
    function G1(e) {
      var t = e.ref;
      if (t !== null) {
        var a = e.stateNode, i;
        switch (e.tag) {
          case B:
            i = a;
            break;
          default:
            i = a;
        }
        if (typeof t == "function") {
          var l;
          if (e.mode & zt)
            try {
              fl(), l = t(i);
            } finally {
              cl(e);
            }
          else
            l = t(i);
          typeof l == "function" && g("Unexpected return value from a callback ref in %s. A callback ref should not return a function.", ht(e));
        } else
          t.hasOwnProperty("current") || g("Unexpected ref object provided for %s. Use either a ref-setter function or React.createRef().", ht(e)), t.current = i;
      }
    }
    function CO(e) {
      var t = e.alternate;
      t !== null && (t.return = null), e.return = null;
    }
    function Q1(e) {
      var t = e.alternate;
      t !== null && (e.alternate = null, Q1(t));
      {
        if (e.child = null, e.deletions = null, e.sibling = null, e.tag === B) {
          var a = e.stateNode;
          a !== null && __(a);
        }
        e.stateNode = null, e._debugOwner = null, e.return = null, e.dependencies = null, e.memoizedProps = null, e.memoizedState = null, e.pendingProps = null, e.stateNode = null, e.updateQueue = null;
      }
    }
    function bO(e) {
      for (var t = e.return; t !== null; ) {
        if (q1(t))
          return t;
        t = t.return;
      }
      throw new Error("Expected to find a host parent. This error is likely caused by a bug in React. Please file an issue.");
    }
    function q1(e) {
      return e.tag === B || e.tag === U || e.tag === te;
    }
    function K1(e) {
      var t = e;
      e: for (; ; ) {
        for (; t.sibling === null; ) {
          if (t.return === null || q1(t.return))
            return null;
          t = t.return;
        }
        for (t.sibling.return = t.return, t = t.sibling; t.tag !== B && t.tag !== M && t.tag !== ge; ) {
          if (t.flags & Kn || t.child === null || t.tag === te)
            continue e;
          t.child.return = t, t = t.child;
        }
        if (!(t.flags & Kn))
          return t.stateNode;
      }
    }
    function TO(e) {
      var t = bO(e);
      switch (t.tag) {
        case B: {
          var a = t.stateNode;
          t.flags & sn && (JC(a), t.flags &= -33);
          var i = K1(e);
          aE(e, i, a);
          break;
        }
        case U:
        case te: {
          var l = t.stateNode.containerInfo, c = K1(e);
          rE(e, c, l);
          break;
        }
        default:
          throw new Error("Invalid host parent fiber. This error is likely caused by a bug in React. Please file an issue.");
      }
    }
    function rE(e, t, a) {
      var i = e.tag, l = i === B || i === M;
      if (l) {
        var c = e.stateNode;
        t ? Vx(a, c, t) : jx(a, c);
      } else if (i !== te) {
        var p = e.child;
        if (p !== null) {
          rE(p, t, a);
          for (var m = p.sibling; m !== null; )
            rE(m, t, a), m = m.sibling;
        }
      }
    }
    function aE(e, t, a) {
      var i = e.tag, l = i === B || i === M;
      if (l) {
        var c = e.stateNode;
        t ? Hx(a, c, t) : Fx(a, c);
      } else if (i !== te) {
        var p = e.child;
        if (p !== null) {
          aE(p, t, a);
          for (var m = p.sibling; m !== null; )
            aE(m, t, a), m = m.sibling;
        }
      }
    }
    var na = null, ko = !1;
    function RO(e, t, a) {
      {
        var i = t;
        e: for (; i !== null; ) {
          switch (i.tag) {
            case B: {
              na = i.stateNode, ko = !1;
              break e;
            }
            case U: {
              na = i.stateNode.containerInfo, ko = !0;
              break e;
            }
            case te: {
              na = i.stateNode.containerInfo, ko = !0;
              break e;
            }
          }
          i = i.return;
        }
        if (na === null)
          throw new Error("Expected to find a host parent. This error is likely caused by a bug in React. Please file an issue.");
        X1(e, t, a), na = null, ko = !1;
      }
      CO(a);
    }
    function ps(e, t, a) {
      for (var i = a.child; i !== null; )
        X1(e, t, i), i = i.sibling;
    }
    function X1(e, t, a) {
      switch (Pu(a), a.tag) {
        case B:
          ta || Rd(a, t);
        case M: {
          {
            var i = na, l = ko;
            na = null, ps(e, t, a), na = i, ko = l, na !== null && (ko ? Ix(na, a.stateNode) : Bx(na, a.stateNode));
          }
          return;
        }
        case ge: {
          na !== null && (ko ? Yx(na, a.stateNode) : h0(na, a.stateNode));
          return;
        }
        case te: {
          {
            var c = na, p = ko;
            na = a.stateNode.containerInfo, ko = !0, ps(e, t, a), na = c, ko = p;
          }
          return;
        }
        case z:
        case ue:
        case Ce:
        case Ge: {
          if (!ta) {
            var m = a.updateQueue;
            if (m !== null) {
              var E = m.lastEffect;
              if (E !== null) {
                var R = E.next, w = R;
                do {
                  var V = w, $ = V.destroy, X = V.tag;
                  $ !== void 0 && ((X & ll) !== oi ? My(a, t, $) : (X & Dr) !== oi && (hp(a), a.mode & zt ? (fl(), My(a, t, $), cl(a)) : My(a, t, $), $u())), w = w.next;
                } while (w !== R);
              }
            }
          }
          ps(e, t, a);
          return;
        }
        case A: {
          if (!ta) {
            Rd(a, t);
            var Z = a.stateNode;
            typeof Z.componentWillUnmount == "function" && nE(a, t, Z);
          }
          ps(e, t, a);
          return;
        }
        case Qe: {
          ps(e, t, a);
          return;
        }
        case Pe: {
          if (
            // TODO: Remove this dead flag
            a.mode & Dt
          ) {
            var ne = ta;
            ta = ne || a.memoizedState !== null, ps(e, t, a), ta = ne;
          } else
            ps(e, t, a);
          break;
        }
        default: {
          ps(e, t, a);
          return;
        }
      }
    }
    function wO(e) {
      e.memoizedState;
    }
    function xO(e, t) {
      var a = t.memoizedState;
      if (a === null) {
        var i = t.alternate;
        if (i !== null) {
          var l = i.memoizedState;
          if (l !== null) {
            var c = l.dehydrated;
            c !== null && c_(c);
          }
        }
      }
    }
    function J1(e) {
      var t = e.updateQueue;
      if (t !== null) {
        e.updateQueue = null;
        var a = e.stateNode;
        a === null && (a = e.stateNode = new sO()), t.forEach(function(i) {
          var l = bD.bind(null, e, i);
          if (!a.has(i)) {
            if (a.add(i), Hr)
              if (bd !== null && Td !== null)
                $v(Td, bd);
              else
                throw Error("Expected finished root and lanes to be set. This is a bug in React.");
            i.then(l, l);
          }
        });
      }
    }
    function _O(e, t, a) {
      bd = a, Td = e, on(t), Z1(t, e), on(t), bd = null, Td = null;
    }
    function Oo(e, t, a) {
      var i = t.deletions;
      if (i !== null)
        for (var l = 0; l < i.length; l++) {
          var c = i[l];
          try {
            RO(e, t, c);
          } catch (E) {
            _n(c, t, E);
          }
        }
      var p = hi();
      if (t.subtreeFlags & zu)
        for (var m = t.child; m !== null; )
          on(m), Z1(m, e), m = m.sibling;
      on(p);
    }
    function Z1(e, t, a) {
      var i = e.alternate, l = e.flags;
      switch (e.tag) {
        case z:
        case ue:
        case Ce:
        case Ge: {
          if (Oo(t, e), dl(e), l & At) {
            try {
              _o(ll | Or, e, e.return), ds(ll | Or, e);
            } catch (dt) {
              _n(e, e.return, dt);
            }
            if (e.mode & zt) {
              try {
                fl(), _o(Dr | Or, e, e.return);
              } catch (dt) {
                _n(e, e.return, dt);
              }
              cl(e);
            } else
              try {
                _o(Dr | Or, e, e.return);
              } catch (dt) {
                _n(e, e.return, dt);
              }
          }
          return;
        }
        case A: {
          Oo(t, e), dl(e), l & Xn && i !== null && Rd(i, i.return);
          return;
        }
        case B: {
          Oo(t, e), dl(e), l & Xn && i !== null && Rd(i, i.return);
          {
            if (e.flags & sn) {
              var c = e.stateNode;
              try {
                JC(c);
              } catch (dt) {
                _n(e, e.return, dt);
              }
            }
            if (l & At) {
              var p = e.stateNode;
              if (p != null) {
                var m = e.memoizedProps, E = i !== null ? i.memoizedProps : m, R = e.type, w = e.updateQueue;
                if (e.updateQueue = null, w !== null)
                  try {
                    Px(p, w, R, E, m, e);
                  } catch (dt) {
                    _n(e, e.return, dt);
                  }
              }
            }
          }
          return;
        }
        case M: {
          if (Oo(t, e), dl(e), l & At) {
            if (e.stateNode === null)
              throw new Error("This should have a text node initialized. This error is likely caused by a bug in React. Please file an issue.");
            var V = e.stateNode, $ = e.memoizedProps, X = i !== null ? i.memoizedProps : $;
            try {
              $x(V, X, $);
            } catch (dt) {
              _n(e, e.return, dt);
            }
          }
          return;
        }
        case U: {
          if (Oo(t, e), dl(e), l & At && i !== null) {
            var Z = i.memoizedState;
            if (Z.isDehydrated)
              try {
                s_(t.containerInfo);
              } catch (dt) {
                _n(e, e.return, dt);
              }
          }
          return;
        }
        case te: {
          Oo(t, e), dl(e);
          return;
        }
        case se: {
          Oo(t, e), dl(e);
          var ne = e.child;
          if (ne.flags & Fi) {
            var Me = ne.stateNode, lt = ne.memoizedState, tt = lt !== null;
            if (Me.isHidden = tt, tt) {
              var jt = ne.alternate !== null && ne.alternate.memoizedState !== null;
              jt || lD();
            }
          }
          if (l & At) {
            try {
              wO(e);
            } catch (dt) {
              _n(e, e.return, dt);
            }
            J1(e);
          }
          return;
        }
        case Pe: {
          var Lt = i !== null && i.memoizedState !== null;
          if (
            // TODO: Remove this dead flag
            e.mode & Dt
          ) {
            var W = ta;
            ta = W || Lt, Oo(t, e), ta = W;
          } else
            Oo(t, e);
          if (dl(e), l & Fi) {
            var re = e.stateNode, G = e.memoizedState, me = G !== null, We = e;
            if (re.isHidden = me, me && !Lt && (We.mode & Dt) !== rt) {
              Je = We;
              for (var Fe = We.child; Fe !== null; )
                Je = Fe, OO(Fe), Fe = Fe.sibling;
            }
            EO(We, me);
          }
          return;
        }
        case je: {
          Oo(t, e), dl(e), l & At && J1(e);
          return;
        }
        case Qe:
          return;
        default: {
          Oo(t, e), dl(e);
          return;
        }
      }
    }
    function dl(e) {
      var t = e.flags;
      if (t & Kn) {
        try {
          TO(e);
        } catch (a) {
          _n(e, e.return, a);
        }
        e.flags &= -3;
      }
      t & Jn && (e.flags &= -4097);
    }
    function kO(e, t, a) {
      bd = a, Td = t, Je = e, eT(e, t, a), bd = null, Td = null;
    }
    function eT(e, t, a) {
      for (var i = (e.mode & Dt) !== rt; Je !== null; ) {
        var l = Je, c = l.child;
        if (l.tag === Pe && i) {
          var p = l.memoizedState !== null, m = p || Ay;
          if (m) {
            iE(e, t, a);
            continue;
          } else {
            var E = l.alternate, R = E !== null && E.memoizedState !== null, w = R || ta, V = Ay, $ = ta;
            Ay = m, ta = w, ta && !$ && (Je = l, DO(l));
            for (var X = c; X !== null; )
              Je = X, eT(
                X,
                // New root; bubble back up to here and stop.
                t,
                a
              ), X = X.sibling;
            Je = l, Ay = V, ta = $, iE(e, t, a);
            continue;
          }
        }
        (l.subtreeFlags & Bo) !== nt && c !== null ? (c.return = l, Je = c) : iE(e, t, a);
      }
    }
    function iE(e, t, a) {
      for (; Je !== null; ) {
        var i = Je;
        if ((i.flags & Bo) !== nt) {
          var l = i.alternate;
          on(i);
          try {
            gO(t, l, i, a);
          } catch (p) {
            _n(i, i.return, p);
          }
          zn();
        }
        if (i === e) {
          Je = null;
          return;
        }
        var c = i.sibling;
        if (c !== null) {
          c.return = i.return, Je = c;
          return;
        }
        Je = i.return;
      }
    }
    function OO(e) {
      for (; Je !== null; ) {
        var t = Je, a = t.child;
        switch (t.tag) {
          case z:
          case ue:
          case Ce:
          case Ge: {
            if (t.mode & zt)
              try {
                fl(), _o(Dr, t, t.return);
              } finally {
                cl(t);
              }
            else
              _o(Dr, t, t.return);
            break;
          }
          case A: {
            Rd(t, t.return);
            var i = t.stateNode;
            typeof i.componentWillUnmount == "function" && nE(t, t.return, i);
            break;
          }
          case B: {
            Rd(t, t.return);
            break;
          }
          case Pe: {
            var l = t.memoizedState !== null;
            if (l) {
              tT(e);
              continue;
            }
            break;
          }
        }
        a !== null ? (a.return = t, Je = a) : tT(e);
      }
    }
    function tT(e) {
      for (; Je !== null; ) {
        var t = Je;
        if (t === e) {
          Je = null;
          return;
        }
        var a = t.sibling;
        if (a !== null) {
          a.return = t.return, Je = a;
          return;
        }
        Je = t.return;
      }
    }
    function DO(e) {
      for (; Je !== null; ) {
        var t = Je, a = t.child;
        if (t.tag === Pe) {
          var i = t.memoizedState !== null;
          if (i) {
            nT(e);
            continue;
          }
        }
        a !== null ? (a.return = t, Je = a) : nT(e);
      }
    }
    function nT(e) {
      for (; Je !== null; ) {
        var t = Je;
        on(t);
        try {
          SO(t);
        } catch (i) {
          _n(t, t.return, i);
        }
        if (zn(), t === e) {
          Je = null;
          return;
        }
        var a = t.sibling;
        if (a !== null) {
          a.return = t.return, Je = a;
          return;
        }
        Je = t.return;
      }
    }
    function NO(e, t, a, i) {
      Je = t, AO(t, e, a, i);
    }
    function AO(e, t, a, i) {
      for (; Je !== null; ) {
        var l = Je, c = l.child;
        (l.subtreeFlags & Rr) !== nt && c !== null ? (c.return = l, Je = c) : MO(e, t, a, i);
      }
    }
    function MO(e, t, a, i) {
      for (; Je !== null; ) {
        var l = Je;
        if ((l.flags & Aa) !== nt) {
          on(l);
          try {
            LO(t, l, a, i);
          } catch (p) {
            _n(l, l.return, p);
          }
          zn();
        }
        if (l === e) {
          Je = null;
          return;
        }
        var c = l.sibling;
        if (c !== null) {
          c.return = l.return, Je = c;
          return;
        }
        Je = l.return;
      }
    }
    function LO(e, t, a, i) {
      switch (t.tag) {
        case z:
        case ue:
        case Ge: {
          if (t.mode & zt) {
            RS();
            try {
              ds(Zr | Or, t);
            } finally {
              TS(t);
            }
          } else
            ds(Zr | Or, t);
          break;
        }
      }
    }
    function zO(e) {
      Je = e, UO();
    }
    function UO() {
      for (; Je !== null; ) {
        var e = Je, t = e.child;
        if ((Je.flags & pa) !== nt) {
          var a = e.deletions;
          if (a !== null) {
            for (var i = 0; i < a.length; i++) {
              var l = a[i];
              Je = l, FO(l, e);
            }
            {
              var c = e.alternate;
              if (c !== null) {
                var p = c.child;
                if (p !== null) {
                  c.child = null;
                  do {
                    var m = p.sibling;
                    p.sibling = null, p = m;
                  } while (p !== null);
                }
              }
            }
            Je = e;
          }
        }
        (e.subtreeFlags & Rr) !== nt && t !== null ? (t.return = e, Je = t) : PO();
      }
    }
    function PO() {
      for (; Je !== null; ) {
        var e = Je;
        (e.flags & Aa) !== nt && (on(e), $O(e), zn());
        var t = e.sibling;
        if (t !== null) {
          t.return = e.return, Je = t;
          return;
        }
        Je = e.return;
      }
    }
    function $O(e) {
      switch (e.tag) {
        case z:
        case ue:
        case Ge: {
          e.mode & zt ? (RS(), _o(Zr | Or, e, e.return), TS(e)) : _o(Zr | Or, e, e.return);
          break;
        }
      }
    }
    function FO(e, t) {
      for (; Je !== null; ) {
        var a = Je;
        on(a), HO(a, t), zn();
        var i = a.child;
        i !== null ? (i.return = a, Je = i) : jO(e);
      }
    }
    function jO(e) {
      for (; Je !== null; ) {
        var t = Je, a = t.sibling, i = t.return;
        if (Q1(t), t === e) {
          Je = null;
          return;
        }
        if (a !== null) {
          a.return = i, Je = a;
          return;
        }
        Je = i;
      }
    }
    function HO(e, t) {
      switch (e.tag) {
        case z:
        case ue:
        case Ge: {
          e.mode & zt ? (RS(), _o(Zr, e, t), TS(e)) : _o(Zr, e, t);
          break;
        }
      }
    }
    function VO(e) {
      switch (e.tag) {
        case z:
        case ue:
        case Ge: {
          try {
            ds(Dr | Or, e);
          } catch (a) {
            _n(e, e.return, a);
          }
          break;
        }
        case A: {
          var t = e.stateNode;
          try {
            t.componentDidMount();
          } catch (a) {
            _n(e, e.return, a);
          }
          break;
        }
      }
    }
    function BO(e) {
      switch (e.tag) {
        case z:
        case ue:
        case Ge: {
          try {
            ds(Zr | Or, e);
          } catch (t) {
            _n(e, e.return, t);
          }
          break;
        }
      }
    }
    function IO(e) {
      switch (e.tag) {
        case z:
        case ue:
        case Ge: {
          try {
            _o(Dr | Or, e, e.return);
          } catch (a) {
            _n(e, e.return, a);
          }
          break;
        }
        case A: {
          var t = e.stateNode;
          typeof t.componentWillUnmount == "function" && nE(e, e.return, t);
          break;
        }
      }
    }
    function YO(e) {
      switch (e.tag) {
        case z:
        case ue:
        case Ge:
          try {
            _o(Zr | Or, e, e.return);
          } catch (t) {
            _n(e, e.return, t);
          }
      }
    }
    if (typeof Symbol == "function" && Symbol.for) {
      var _v = Symbol.for;
      _v("selector.component"), _v("selector.has_pseudo_class"), _v("selector.role"), _v("selector.test_id"), _v("selector.text");
    }
    var WO = [];
    function GO() {
      WO.forEach(function(e) {
        return e();
      });
    }
    var QO = y.ReactCurrentActQueue;
    function qO(e) {
      {
        var t = (
          // $FlowExpectedError – Flow doesn't know about IS_REACT_ACT_ENVIRONMENT global
          typeof IS_REACT_ACT_ENVIRONMENT < "u" ? IS_REACT_ACT_ENVIRONMENT : void 0
        ), a = typeof jest < "u";
        return a && t !== !1;
      }
    }
    function rT() {
      {
        var e = (
          // $FlowExpectedError – Flow doesn't know about IS_REACT_ACT_ENVIRONMENT global
          typeof IS_REACT_ACT_ENVIRONMENT < "u" ? IS_REACT_ACT_ENVIRONMENT : void 0
        );
        return !e && QO.current !== null && g("The current testing environment is not configured to support act(...)"), e;
      }
    }
    var KO = Math.ceil, oE = y.ReactCurrentDispatcher, lE = y.ReactCurrentOwner, ra = y.ReactCurrentBatchConfig, Do = y.ReactCurrentActQueue, Mr = (
      /*             */
      0
    ), aT = (
      /*               */
      1
    ), aa = (
      /*                */
      2
    ), Ki = (
      /*                */
      4
    ), lu = 0, kv = 1, Mc = 2, Ly = 3, Ov = 4, iT = 5, uE = 6, Ft = Mr, ja = null, Wn = null, Lr = oe, pl = oe, sE = rs(oe), zr = lu, Dv = null, zy = oe, Nv = oe, Uy = oe, Av = null, li = null, cE = 0, oT = 500, lT = 1 / 0, XO = 500, uu = null;
    function Mv() {
      lT = Vn() + XO;
    }
    function uT() {
      return lT;
    }
    var Py = !1, fE = null, wd = null, Lc = !1, vs = null, Lv = oe, dE = [], pE = null, JO = 50, zv = 0, vE = null, hE = !1, $y = !1, ZO = 50, xd = 0, Fy = null, Uv = tn, jy = oe, sT = !1;
    function Hy() {
      return ja;
    }
    function Ha() {
      return (Ft & (aa | Ki)) !== Mr ? Vn() : (Uv !== tn || (Uv = Vn()), Uv);
    }
    function hs(e) {
      var t = e.mode;
      if ((t & Dt) === rt)
        return ct;
      if ((Ft & aa) !== Mr && Lr !== oe)
        return gr(Lr);
      var a = Q_() !== G_;
      if (a) {
        if (ra.transition !== null) {
          var i = ra.transition;
          i._updatedFibers || (i._updatedFibers = /* @__PURE__ */ new Set()), i._updatedFibers.add(e);
        }
        return jy === er && (jy = wp()), jy;
      }
      var l = za();
      if (l !== er)
        return l;
      var c = Ax();
      return c;
    }
    function eD(e) {
      var t = e.mode;
      return (t & Dt) === rt ? ct : Kh();
    }
    function Ur(e, t, a, i) {
      RD(), sT && g("useInsertionEffect must not schedule updates."), hE && ($y = !0), Iu(e, a, i), (Ft & aa) !== oe && e === ja ? _D(t) : (Hr && Jh(e, t, a), kD(t), e === ja && ((Ft & aa) === Mr && (Nv = Tt(Nv, a)), zr === Ov && ms(e, Lr)), ui(e, i), a === ct && Ft === Mr && (t.mode & Dt) === rt && // Treat `act` as if it's inside `batchedUpdates`, even in legacy mode.
      !Do.isBatchingLegacy && (Mv(), sb()));
    }
    function tD(e, t, a) {
      var i = e.current;
      i.lanes = t, Iu(e, t, a), ui(e, a);
    }
    function nD(e) {
      return (
        // TODO: Remove outdated deferRenderPhaseUpdateToNextBatch experiment. We
        // decided not to enable it.
        (Ft & aa) !== Mr
      );
    }
    function ui(e, t) {
      var a = e.callbackNode;
      Gh(e, t);
      var i = ya(e, e === ja ? Lr : oe);
      if (i === oe) {
        a !== null && wT(a), e.callbackNode = null, e.callbackPriority = er;
        return;
      }
      var l = Vl(i), c = e.callbackPriority;
      if (c === l && // Special case related to `act`. If the currently scheduled task is a
      // Scheduler task, rather than an `act` task, cancel it and re-scheduled
      // on the `act` queue.
      !(Do.current !== null && a !== bE)) {
        a == null && c !== ct && g("Expected scheduled callback to exist. This error is likely caused by a bug in React. Please file an issue.");
        return;
      }
      a != null && wT(a);
      var p;
      if (l === ct)
        e.tag === as ? (Do.isBatchingLegacy !== null && (Do.didScheduleLegacyUpdate = !0), D_(dT.bind(null, e))) : ub(dT.bind(null, e)), Do.current !== null ? Do.current.push(is) : Lx(function() {
          (Ft & (aa | Ki)) === Mr && is();
        }), p = null;
      else {
        var m;
        switch (em(i)) {
          case Sa:
            m = mo;
            break;
          case ei:
            m = Ys;
            break;
          case xr:
            m = Ul;
            break;
          case Pf:
            m = Uu;
            break;
          default:
            m = Ul;
            break;
        }
        p = TE(m, cT.bind(null, e));
      }
      e.callbackPriority = l, e.callbackNode = p;
    }
    function cT(e, t) {
      if (Ek(), Uv = tn, jy = oe, (Ft & (aa | Ki)) !== Mr)
        throw new Error("Should not already be working.");
      var a = e.callbackNode, i = cu();
      if (i && e.callbackNode !== a)
        return null;
      var l = ya(e, e === ja ? Lr : oe);
      if (l === oe)
        return null;
      var c = !rc(e, l) && !qh(e, l) && !t, p = c ? dD(e, l) : By(e, l);
      if (p !== lu) {
        if (p === Mc) {
          var m = Of(e);
          m !== oe && (l = m, p = mE(e, m));
        }
        if (p === kv) {
          var E = Dv;
          throw zc(e, oe), ms(e, l), ui(e, Vn()), E;
        }
        if (p === uE)
          ms(e, l);
        else {
          var R = !rc(e, l), w = e.current.alternate;
          if (R && !aD(w)) {
            if (p = By(e, l), p === Mc) {
              var V = Of(e);
              V !== oe && (l = V, p = mE(e, V));
            }
            if (p === kv) {
              var $ = Dv;
              throw zc(e, oe), ms(e, l), ui(e, Vn()), $;
            }
          }
          e.finishedWork = w, e.finishedLanes = l, rD(e, p, l);
        }
      }
      return ui(e, Vn()), e.callbackNode === a ? cT.bind(null, e) : null;
    }
    function mE(e, t) {
      var a = Av;
      if (Il(e)) {
        var i = zc(e, t);
        i.flags |= Un, T_(e.containerInfo);
      }
      var l = By(e, t);
      if (l !== Mc) {
        var c = li;
        li = a, c !== null && fT(c);
      }
      return l;
    }
    function fT(e) {
      li === null ? li = e : li.push.apply(li, e);
    }
    function rD(e, t, a) {
      switch (t) {
        case lu:
        case kv:
          throw new Error("Root did not complete. This is a bug in React.");
        case Mc: {
          Uc(e, li, uu);
          break;
        }
        case Ly: {
          if (ms(e, a), Df(a) && // do not delay if we're inside an act() scope
          !xT()) {
            var i = cE + oT - Vn();
            if (i > 10) {
              var l = ya(e, oe);
              if (l !== oe)
                break;
              var c = e.suspendedLanes;
              if (!Bl(c, a)) {
                Ha(), Lf(e, c);
                break;
              }
              e.timeoutHandle = p0(Uc.bind(null, e, li, uu), i);
              break;
            }
          }
          Uc(e, li, uu);
          break;
        }
        case Ov: {
          if (ms(e, a), $g(a))
            break;
          if (!xT()) {
            var p = Cp(e, a), m = p, E = Vn() - m, R = TD(E) - E;
            if (R > 10) {
              e.timeoutHandle = p0(Uc.bind(null, e, li, uu), R);
              break;
            }
          }
          Uc(e, li, uu);
          break;
        }
        case iT: {
          Uc(e, li, uu);
          break;
        }
        default:
          throw new Error("Unknown root exit status.");
      }
    }
    function aD(e) {
      for (var t = e; ; ) {
        if (t.flags & of) {
          var a = t.updateQueue;
          if (a !== null) {
            var i = a.stores;
            if (i !== null)
              for (var l = 0; l < i.length; l++) {
                var c = i[l], p = c.getSnapshot, m = c.value;
                try {
                  if (!$e(p(), m))
                    return !1;
                } catch {
                  return !1;
                }
              }
          }
        }
        var E = t.child;
        if (t.subtreeFlags & of && E !== null) {
          E.return = t, t = E;
          continue;
        }
        if (t === e)
          return !0;
        for (; t.sibling === null; ) {
          if (t.return === null || t.return === e)
            return !0;
          t = t.return;
        }
        t.sibling.return = t.return, t = t.sibling;
      }
      return !0;
    }
    function ms(e, t) {
      t = ac(t, Uy), t = ac(t, Nv), _p(e, t);
    }
    function dT(e) {
      if (Ck(), (Ft & (aa | Ki)) !== Mr)
        throw new Error("Should not already be working.");
      cu();
      var t = ya(e, oe);
      if (!ga(t, ct))
        return ui(e, Vn()), null;
      var a = By(e, t);
      if (e.tag !== as && a === Mc) {
        var i = Of(e);
        i !== oe && (t = i, a = mE(e, i));
      }
      if (a === kv) {
        var l = Dv;
        throw zc(e, oe), ms(e, t), ui(e, Vn()), l;
      }
      if (a === uE)
        throw new Error("Root did not complete. This is a bug in React.");
      var c = e.current.alternate;
      return e.finishedWork = c, e.finishedLanes = t, Uc(e, li, uu), ui(e, Vn()), null;
    }
    function iD(e, t) {
      t !== oe && (ic(e, Tt(t, ct)), ui(e, Vn()), (Ft & (aa | Ki)) === Mr && (Mv(), is()));
    }
    function yE(e, t) {
      var a = Ft;
      Ft |= aT;
      try {
        return e(t);
      } finally {
        Ft = a, Ft === Mr && // Treat `act` as if it's inside `batchedUpdates`, even in legacy mode.
        !Do.isBatchingLegacy && (Mv(), sb());
      }
    }
    function oD(e, t, a, i, l) {
      var c = za(), p = ra.transition;
      try {
        return ra.transition = null, lr(Sa), e(t, a, i, l);
      } finally {
        lr(c), ra.transition = p, Ft === Mr && Mv();
      }
    }
    function su(e) {
      vs !== null && vs.tag === as && (Ft & (aa | Ki)) === Mr && cu();
      var t = Ft;
      Ft |= aT;
      var a = ra.transition, i = za();
      try {
        return ra.transition = null, lr(Sa), e ? e() : void 0;
      } finally {
        lr(i), ra.transition = a, Ft = t, (Ft & (aa | Ki)) === Mr && is();
      }
    }
    function pT() {
      return (Ft & (aa | Ki)) !== Mr;
    }
    function Vy(e, t) {
      ba(sE, pl, e), pl = Tt(pl, t);
    }
    function gE(e) {
      pl = sE.current, Ca(sE, e);
    }
    function zc(e, t) {
      e.finishedWork = null, e.finishedLanes = oe;
      var a = e.timeoutHandle;
      if (a !== v0 && (e.timeoutHandle = v0, Mx(a)), Wn !== null)
        for (var i = Wn.return; i !== null; ) {
          var l = i.alternate;
          V1(l, i), i = i.return;
        }
      ja = e;
      var c = Pc(e.current, null);
      return Wn = c, Lr = pl = t, zr = lu, Dv = null, zy = oe, Nv = oe, Uy = oe, Av = null, li = null, tk(), bo.discardPendingWarnings(), c;
    }
    function vT(e, t) {
      do {
        var a = Wn;
        try {
          if (Jm(), $b(), zn(), lE.current = null, a === null || a.return === null) {
            zr = kv, Dv = t, Wn = null;
            return;
          }
          if (be && a.mode & zt && _y(a, !0), Re)
            if (Yo(), t !== null && typeof t == "object" && typeof t.then == "function") {
              var i = t;
              Gs(a, i, Lr);
            } else
              Vi(a, t, Lr);
          Dk(e, a.return, a, t, Lr), gT(a);
        } catch (l) {
          t = l, Wn === a && a !== null ? (a = a.return, Wn = a) : a = Wn;
          continue;
        }
        return;
      } while (!0);
    }
    function hT() {
      var e = oE.current;
      return oE.current = by, e === null ? by : e;
    }
    function mT(e) {
      oE.current = e;
    }
    function lD() {
      cE = Vn();
    }
    function Pv(e) {
      zy = Tt(e, zy);
    }
    function uD() {
      zr === lu && (zr = Ly);
    }
    function SE() {
      (zr === lu || zr === Ly || zr === Mc) && (zr = Ov), ja !== null && (Ko(zy) || Ko(Nv)) && ms(ja, Lr);
    }
    function sD(e) {
      zr !== Ov && (zr = Mc), Av === null ? Av = [e] : Av.push(e);
    }
    function cD() {
      return zr === lu;
    }
    function By(e, t) {
      var a = Ft;
      Ft |= aa;
      var i = hT();
      if (ja !== e || Lr !== t) {
        if (Hr) {
          var l = e.memoizedUpdaters;
          l.size > 0 && ($v(e, Lr), l.clear()), kp(e, t);
        }
        uu = Uf(), zc(e, t);
      }
      yp(t);
      do
        try {
          fD();
          break;
        } catch (c) {
          vT(e, c);
        }
      while (!0);
      if (Jm(), Ft = a, mT(i), Wn !== null)
        throw new Error("Cannot commit an incomplete root. This error is likely caused by a bug in React. Please file an issue.");
      return Nn(), ja = null, Lr = oe, zr;
    }
    function fD() {
      for (; Wn !== null; )
        yT(Wn);
    }
    function dD(e, t) {
      var a = Ft;
      Ft |= aa;
      var i = hT();
      if (ja !== e || Lr !== t) {
        if (Hr) {
          var l = e.memoizedUpdaters;
          l.size > 0 && ($v(e, Lr), l.clear()), kp(e, t);
        }
        uu = Uf(), Mv(), zc(e, t);
      }
      yp(t);
      do
        try {
          pD();
          break;
        } catch (c) {
          vT(e, c);
        }
      while (!0);
      return Jm(), mT(i), Ft = a, Wn !== null ? (gp(), lu) : (Nn(), ja = null, Lr = oe, zr);
    }
    function pD() {
      for (; Wn !== null && !sp(); )
        yT(Wn);
    }
    function yT(e) {
      var t = e.alternate;
      on(e);
      var a;
      (e.mode & zt) !== rt ? (bS(e), a = EE(t, e, pl), _y(e, !0)) : a = EE(t, e, pl), zn(), e.memoizedProps = e.pendingProps, a === null ? gT(e) : Wn = a, lE.current = null;
    }
    function gT(e) {
      var t = e;
      do {
        var a = t.alternate, i = t.return;
        if ((t.flags & Ll) === nt) {
          on(t);
          var l = void 0;
          if ((t.mode & zt) === rt ? l = H1(a, t, pl) : (bS(t), l = H1(a, t, pl), _y(t, !1)), zn(), l !== null) {
            Wn = l;
            return;
          }
        } else {
          var c = uO(a, t);
          if (c !== null) {
            c.flags &= zh, Wn = c;
            return;
          }
          if ((t.mode & zt) !== rt) {
            _y(t, !1);
            for (var p = t.actualDuration, m = t.child; m !== null; )
              p += m.actualDuration, m = m.sibling;
            t.actualDuration = p;
          }
          if (i !== null)
            i.flags |= Ll, i.subtreeFlags = nt, i.deletions = null;
          else {
            zr = uE, Wn = null;
            return;
          }
        }
        var E = t.sibling;
        if (E !== null) {
          Wn = E;
          return;
        }
        t = i, Wn = t;
      } while (t !== null);
      zr === lu && (zr = iT);
    }
    function Uc(e, t, a) {
      var i = za(), l = ra.transition;
      try {
        ra.transition = null, lr(Sa), vD(e, t, a, i);
      } finally {
        ra.transition = l, lr(i);
      }
      return null;
    }
    function vD(e, t, a, i) {
      do
        cu();
      while (vs !== null);
      if (wD(), (Ft & (aa | Ki)) !== Mr)
        throw new Error("Should not already be working.");
      var l = e.finishedWork, c = e.finishedLanes;
      if (Hh(c), l === null)
        return Hi(), null;
      if (c === oe && g("root.finishedLanes should not be empty during a commit. This is a bug in React."), e.finishedWork = null, e.finishedLanes = oe, l === e.current)
        throw new Error("Cannot commit the same tree as before. This error is likely caused by a bug in React. Please file an issue.");
      e.callbackNode = null, e.callbackPriority = er;
      var p = Tt(l.lanes, l.childLanes);
      Xh(e, p), e === ja && (ja = null, Wn = null, Lr = oe), ((l.subtreeFlags & Rr) !== nt || (l.flags & Rr) !== nt) && (Lc || (Lc = !0, pE = a, TE(Ul, function() {
        return cu(), null;
      })));
      var m = (l.subtreeFlags & (Vo | zu | Bo | Rr)) !== nt, E = (l.flags & (Vo | zu | Bo | Rr)) !== nt;
      if (m || E) {
        var R = ra.transition;
        ra.transition = null;
        var w = za();
        lr(Sa);
        var V = Ft;
        Ft |= Ki, lE.current = null, pO(e, l), s1(), _O(e, l, c), xx(e.containerInfo), e.current = l, Qs(c), kO(l, e, c), $l(), Ph(), Ft = V, lr(w), ra.transition = R;
      } else
        e.current = l, s1();
      var $ = Lc;
      if (Lc ? (Lc = !1, vs = e, Lv = c) : (xd = 0, Fy = null), p = e.pendingLanes, p === oe && (wd = null), $ || bT(e.current, !1), dp(l.stateNode, i), Hr && e.memoizedUpdaters.clear(), GO(), ui(e, Vn()), t !== null)
        for (var X = e.onRecoverableError, Z = 0; Z < t.length; Z++) {
          var ne = t[Z], Me = ne.stack, lt = ne.digest;
          X(ne.value, {
            componentStack: Me,
            digest: lt
          });
        }
      if (Py) {
        Py = !1;
        var tt = fE;
        throw fE = null, tt;
      }
      return ga(Lv, ct) && e.tag !== as && cu(), p = e.pendingLanes, ga(p, ct) ? (Sk(), e === vE ? zv++ : (zv = 0, vE = e)) : zv = 0, is(), Hi(), null;
    }
    function cu() {
      if (vs !== null) {
        var e = em(Lv), t = Vr(xr, e), a = ra.transition, i = za();
        try {
          return ra.transition = null, lr(t), mD();
        } finally {
          lr(i), ra.transition = a;
        }
      }
      return !1;
    }
    function hD(e) {
      dE.push(e), Lc || (Lc = !0, TE(Ul, function() {
        return cu(), null;
      }));
    }
    function mD() {
      if (vs === null)
        return !1;
      var e = pE;
      pE = null;
      var t = vs, a = Lv;
      if (vs = null, Lv = oe, (Ft & (aa | Ki)) !== Mr)
        throw new Error("Cannot flush passive effects while already rendering.");
      hE = !0, $y = !1, mp(a);
      var i = Ft;
      Ft |= Ki, zO(t.current), NO(t, t.current, a, e);
      {
        var l = dE;
        dE = [];
        for (var c = 0; c < l.length; c++) {
          var p = l[c];
          yO(t, p);
        }
      }
      Fu(), bT(t.current, !0), Ft = i, is(), $y ? t === Fy ? xd++ : (xd = 0, Fy = t) : xd = 0, hE = !1, $y = !1, pp(t);
      {
        var m = t.current.stateNode;
        m.effectDuration = 0, m.passiveEffectDuration = 0;
      }
      return !0;
    }
    function ST(e) {
      return wd !== null && wd.has(e);
    }
    function yD(e) {
      wd === null ? wd = /* @__PURE__ */ new Set([e]) : wd.add(e);
    }
    function gD(e) {
      Py || (Py = !0, fE = e);
    }
    var SD = gD;
    function ET(e, t, a) {
      var i = Nc(a, t), l = y1(e, i, ct), c = ls(e, l, ct), p = Ha();
      c !== null && (Iu(c, ct, p), ui(c, p));
    }
    function _n(e, t, a) {
      if (cO(a), Fv(!1), e.tag === U) {
        ET(e, e, a);
        return;
      }
      var i = null;
      for (i = t; i !== null; ) {
        if (i.tag === U) {
          ET(i, e, a);
          return;
        } else if (i.tag === A) {
          var l = i.type, c = i.stateNode;
          if (typeof l.getDerivedStateFromError == "function" || typeof c.componentDidCatch == "function" && !ST(c)) {
            var p = Nc(a, e), m = jS(i, p, ct), E = ls(i, m, ct), R = Ha();
            E !== null && (Iu(E, ct, R), ui(E, R));
            return;
          }
        }
        i = i.return;
      }
      g(`Internal React error: Attempted to capture a commit phase error inside a detached tree. This indicates a bug in React. Likely causes include deleting the same fiber more than once, committing an already-finished tree, or an inconsistent return pointer.

Error message:

%s`, a);
    }
    function ED(e, t, a) {
      var i = e.pingCache;
      i !== null && i.delete(t);
      var l = Ha();
      Lf(e, a), OD(e), ja === e && Bl(Lr, a) && (zr === Ov || zr === Ly && Df(Lr) && Vn() - cE < oT ? zc(e, oe) : Uy = Tt(Uy, a)), ui(e, l);
    }
    function CT(e, t) {
      t === er && (t = eD(e));
      var a = Ha(), i = ii(e, t);
      i !== null && (Iu(i, t, a), ui(i, a));
    }
    function CD(e) {
      var t = e.memoizedState, a = er;
      t !== null && (a = t.retryLane), CT(e, a);
    }
    function bD(e, t) {
      var a = er, i;
      switch (e.tag) {
        case se:
          i = e.stateNode;
          var l = e.memoizedState;
          l !== null && (a = l.retryLane);
          break;
        case je:
          i = e.stateNode;
          break;
        default:
          throw new Error("Pinged unknown suspense boundary type. This is probably a bug in React.");
      }
      i !== null && i.delete(t), CT(e, a);
    }
    function TD(e) {
      return e < 120 ? 120 : e < 480 ? 480 : e < 1080 ? 1080 : e < 1920 ? 1920 : e < 3e3 ? 3e3 : e < 4320 ? 4320 : KO(e / 1960) * 1960;
    }
    function RD() {
      if (zv > JO)
        throw zv = 0, vE = null, new Error("Maximum update depth exceeded. This can happen when a component repeatedly calls setState inside componentWillUpdate or componentDidUpdate. React limits the number of nested updates to prevent infinite loops.");
      xd > ZO && (xd = 0, Fy = null, g("Maximum update depth exceeded. This can happen when a component calls setState inside useEffect, but useEffect either doesn't have a dependency array, or one of the dependencies changes on every render."));
    }
    function wD() {
      bo.flushLegacyContextWarning(), bo.flushPendingUnsafeLifecycleWarnings();
    }
    function bT(e, t) {
      on(e), Iy(e, Qr, IO), t && Iy(e, Ho, YO), Iy(e, Qr, VO), t && Iy(e, Ho, BO), zn();
    }
    function Iy(e, t, a) {
      for (var i = e, l = null; i !== null; ) {
        var c = i.subtreeFlags & t;
        i !== l && i.child !== null && c !== nt ? i = i.child : ((i.flags & t) !== nt && a(i), i.sibling !== null ? i = i.sibling : i = l = i.return);
      }
    }
    var Yy = null;
    function TT(e) {
      {
        if ((Ft & aa) !== Mr || !(e.mode & Dt))
          return;
        var t = e.tag;
        if (t !== F && t !== U && t !== A && t !== z && t !== ue && t !== Ce && t !== Ge)
          return;
        var a = ht(e) || "ReactComponent";
        if (Yy !== null) {
          if (Yy.has(a))
            return;
          Yy.add(a);
        } else
          Yy = /* @__PURE__ */ new Set([a]);
        var i = hr;
        try {
          on(e), g("Can't perform a React state update on a component that hasn't mounted yet. This indicates that you have a side-effect in your render function that asynchronously later calls tries to update the component. Move this work to useEffect instead.");
        } finally {
          i ? on(e) : zn();
        }
      }
    }
    var EE;
    {
      var xD = null;
      EE = function(e, t, a) {
        var i = NT(xD, t);
        try {
          return U1(e, t, a);
        } catch (c) {
          if ($_() || c !== null && typeof c == "object" && typeof c.then == "function")
            throw c;
          if (Jm(), $b(), V1(e, t), NT(t, i), t.mode & zt && bS(t), Ka(null, U1, null, e, t, a), np()) {
            var l = rp();
            typeof l == "object" && l !== null && l._suppressLogging && typeof c == "object" && c !== null && !c._suppressLogging && (c._suppressLogging = !0);
          }
          throw c;
        }
      };
    }
    var RT = !1, CE;
    CE = /* @__PURE__ */ new Set();
    function _D(e) {
      if (fa && !mk())
        switch (e.tag) {
          case z:
          case ue:
          case Ge: {
            var t = Wn && ht(Wn) || "Unknown", a = t;
            if (!CE.has(a)) {
              CE.add(a);
              var i = ht(e) || "Unknown";
              g("Cannot update a component (`%s`) while rendering a different component (`%s`). To locate the bad setState() call inside `%s`, follow the stack trace as described in https://reactjs.org/link/setstate-in-render", i, t, t);
            }
            break;
          }
          case A: {
            RT || (g("Cannot update during an existing state transition (such as within `render`). Render methods should be a pure function of props and state."), RT = !0);
            break;
          }
        }
    }
    function $v(e, t) {
      if (Hr) {
        var a = e.memoizedUpdaters;
        a.forEach(function(i) {
          Jh(e, i, t);
        });
      }
    }
    var bE = {};
    function TE(e, t) {
      {
        var a = Do.current;
        return a !== null ? (a.push(t), bE) : lp(e, t);
      }
    }
    function wT(e) {
      if (e !== bE)
        return up(e);
    }
    function xT() {
      return Do.current !== null;
    }
    function kD(e) {
      {
        if (e.mode & Dt) {
          if (!rT())
            return;
        } else if (!qO() || Ft !== Mr || e.tag !== z && e.tag !== ue && e.tag !== Ge)
          return;
        if (Do.current === null) {
          var t = hr;
          try {
            on(e), g(`An update to %s inside a test was not wrapped in act(...).

When testing, code that causes React state updates should be wrapped into act(...):

act(() => {
  /* fire events that update state */
});
/* assert on the output */

This ensures that you're testing the behavior the user would see in the browser. Learn more at https://reactjs.org/link/wrap-tests-with-act`, ht(e));
          } finally {
            t ? on(e) : zn();
          }
        }
      }
    }
    function OD(e) {
      e.tag !== as && rT() && Do.current === null && g(`A suspended resource finished loading inside a test, but the event was not wrapped in act(...).

When testing, code that resolves suspended data should be wrapped into act(...):

act(() => {
  /* finish loading suspended data */
});
/* assert on the output */

This ensures that you're testing the behavior the user would see in the browser. Learn more at https://reactjs.org/link/wrap-tests-with-act`);
    }
    function Fv(e) {
      sT = e;
    }
    var Xi = null, _d = null, DD = function(e) {
      Xi = e;
    };
    function kd(e) {
      {
        if (Xi === null)
          return e;
        var t = Xi(e);
        return t === void 0 ? e : t.current;
      }
    }
    function RE(e) {
      return kd(e);
    }
    function wE(e) {
      {
        if (Xi === null)
          return e;
        var t = Xi(e);
        if (t === void 0) {
          if (e != null && typeof e.render == "function") {
            var a = kd(e.render);
            if (e.render !== a) {
              var i = {
                $$typeof: fe,
                render: a
              };
              return e.displayName !== void 0 && (i.displayName = e.displayName), i;
            }
          }
          return e;
        }
        return t.current;
      }
    }
    function _T(e, t) {
      {
        if (Xi === null)
          return !1;
        var a = e.elementType, i = t.type, l = !1, c = typeof i == "object" && i !== null ? i.$$typeof : null;
        switch (e.tag) {
          case A: {
            typeof i == "function" && (l = !0);
            break;
          }
          case z: {
            (typeof i == "function" || c === yt) && (l = !0);
            break;
          }
          case ue: {
            (c === fe || c === yt) && (l = !0);
            break;
          }
          case Ce:
          case Ge: {
            (c === kt || c === yt) && (l = !0);
            break;
          }
          default:
            return !1;
        }
        if (l) {
          var p = Xi(a);
          if (p !== void 0 && p === Xi(i))
            return !0;
        }
        return !1;
      }
    }
    function kT(e) {
      {
        if (Xi === null || typeof WeakSet != "function")
          return;
        _d === null && (_d = /* @__PURE__ */ new WeakSet()), _d.add(e);
      }
    }
    var ND = function(e, t) {
      {
        if (Xi === null)
          return;
        var a = t.staleFamilies, i = t.updatedFamilies;
        cu(), su(function() {
          xE(e.current, i, a);
        });
      }
    }, AD = function(e, t) {
      {
        if (e.context !== Ri)
          return;
        cu(), su(function() {
          jv(t, e, null, null);
        });
      }
    };
    function xE(e, t, a) {
      {
        var i = e.alternate, l = e.child, c = e.sibling, p = e.tag, m = e.type, E = null;
        switch (p) {
          case z:
          case Ge:
          case A:
            E = m;
            break;
          case ue:
            E = m.render;
            break;
        }
        if (Xi === null)
          throw new Error("Expected resolveFamily to be set during hot reload.");
        var R = !1, w = !1;
        if (E !== null) {
          var V = Xi(E);
          V !== void 0 && (a.has(V) ? w = !0 : t.has(V) && (p === A ? w = !0 : R = !0));
        }
        if (_d !== null && (_d.has(e) || i !== null && _d.has(i)) && (w = !0), w && (e._debugNeedsRemount = !0), w || R) {
          var $ = ii(e, ct);
          $ !== null && Ur($, e, ct, tn);
        }
        l !== null && !w && xE(l, t, a), c !== null && xE(c, t, a);
      }
    }
    var MD = function(e, t) {
      {
        var a = /* @__PURE__ */ new Set(), i = new Set(t.map(function(l) {
          return l.current;
        }));
        return _E(e.current, i, a), a;
      }
    };
    function _E(e, t, a) {
      {
        var i = e.child, l = e.sibling, c = e.tag, p = e.type, m = null;
        switch (c) {
          case z:
          case Ge:
          case A:
            m = p;
            break;
          case ue:
            m = p.render;
            break;
        }
        var E = !1;
        m !== null && t.has(m) && (E = !0), E ? LD(e, a) : i !== null && _E(i, t, a), l !== null && _E(l, t, a);
      }
    }
    function LD(e, t) {
      {
        var a = zD(e, t);
        if (a)
          return;
        for (var i = e; ; ) {
          switch (i.tag) {
            case B:
              t.add(i.stateNode);
              return;
            case te:
              t.add(i.stateNode.containerInfo);
              return;
            case U:
              t.add(i.stateNode.containerInfo);
              return;
          }
          if (i.return === null)
            throw new Error("Expected to reach root first.");
          i = i.return;
        }
      }
    }
    function zD(e, t) {
      for (var a = e, i = !1; ; ) {
        if (a.tag === B)
          i = !0, t.add(a.stateNode);
        else if (a.child !== null) {
          a.child.return = a, a = a.child;
          continue;
        }
        if (a === e)
          return i;
        for (; a.sibling === null; ) {
          if (a.return === null || a.return === e)
            return i;
          a = a.return;
        }
        a.sibling.return = a.return, a = a.sibling;
      }
      return !1;
    }
    var kE;
    {
      kE = !1;
      try {
        var OT = Object.preventExtensions({});
      } catch {
        kE = !0;
      }
    }
    function UD(e, t, a, i) {
      this.tag = e, this.key = a, this.elementType = null, this.type = null, this.stateNode = null, this.return = null, this.child = null, this.sibling = null, this.index = 0, this.ref = null, this.pendingProps = t, this.memoizedProps = null, this.updateQueue = null, this.memoizedState = null, this.dependencies = null, this.mode = i, this.flags = nt, this.subtreeFlags = nt, this.deletions = null, this.lanes = oe, this.childLanes = oe, this.alternate = null, this.actualDuration = Number.NaN, this.actualStartTime = Number.NaN, this.selfBaseDuration = Number.NaN, this.treeBaseDuration = Number.NaN, this.actualDuration = 0, this.actualStartTime = -1, this.selfBaseDuration = 0, this.treeBaseDuration = 0, this._debugSource = null, this._debugOwner = null, this._debugNeedsRemount = !1, this._debugHookTypes = null, !kE && typeof Object.preventExtensions == "function" && Object.preventExtensions(this);
    }
    var wi = function(e, t, a, i) {
      return new UD(e, t, a, i);
    };
    function OE(e) {
      var t = e.prototype;
      return !!(t && t.isReactComponent);
    }
    function PD(e) {
      return typeof e == "function" && !OE(e) && e.defaultProps === void 0;
    }
    function $D(e) {
      if (typeof e == "function")
        return OE(e) ? A : z;
      if (e != null) {
        var t = e.$$typeof;
        if (t === fe)
          return ue;
        if (t === kt)
          return Ce;
      }
      return F;
    }
    function Pc(e, t) {
      var a = e.alternate;
      a === null ? (a = wi(e.tag, t, e.key, e.mode), a.elementType = e.elementType, a.type = e.type, a.stateNode = e.stateNode, a._debugSource = e._debugSource, a._debugOwner = e._debugOwner, a._debugHookTypes = e._debugHookTypes, a.alternate = e, e.alternate = a) : (a.pendingProps = t, a.type = e.type, a.flags = nt, a.subtreeFlags = nt, a.deletions = null, a.actualDuration = 0, a.actualStartTime = -1), a.flags = e.flags & Zn, a.childLanes = e.childLanes, a.lanes = e.lanes, a.child = e.child, a.memoizedProps = e.memoizedProps, a.memoizedState = e.memoizedState, a.updateQueue = e.updateQueue;
      var i = e.dependencies;
      switch (a.dependencies = i === null ? null : {
        lanes: i.lanes,
        firstContext: i.firstContext
      }, a.sibling = e.sibling, a.index = e.index, a.ref = e.ref, a.selfBaseDuration = e.selfBaseDuration, a.treeBaseDuration = e.treeBaseDuration, a._debugNeedsRemount = e._debugNeedsRemount, a.tag) {
        case F:
        case z:
        case Ge:
          a.type = kd(e.type);
          break;
        case A:
          a.type = RE(e.type);
          break;
        case ue:
          a.type = wE(e.type);
          break;
      }
      return a;
    }
    function FD(e, t) {
      e.flags &= Zn | Kn;
      var a = e.alternate;
      if (a === null)
        e.childLanes = oe, e.lanes = t, e.child = null, e.subtreeFlags = nt, e.memoizedProps = null, e.memoizedState = null, e.updateQueue = null, e.dependencies = null, e.stateNode = null, e.selfBaseDuration = 0, e.treeBaseDuration = 0;
      else {
        e.childLanes = a.childLanes, e.lanes = a.lanes, e.child = a.child, e.subtreeFlags = nt, e.deletions = null, e.memoizedProps = a.memoizedProps, e.memoizedState = a.memoizedState, e.updateQueue = a.updateQueue, e.type = a.type;
        var i = a.dependencies;
        e.dependencies = i === null ? null : {
          lanes: i.lanes,
          firstContext: i.firstContext
        }, e.selfBaseDuration = a.selfBaseDuration, e.treeBaseDuration = a.treeBaseDuration;
      }
      return e;
    }
    function jD(e, t, a) {
      var i;
      return e === Vm ? (i = Dt, t === !0 && (i |= Ct, i |= cn)) : i = rt, Hr && (i |= zt), wi(U, null, null, i);
    }
    function DE(e, t, a, i, l, c) {
      var p = F, m = e;
      if (typeof e == "function")
        OE(e) ? (p = A, m = RE(m)) : m = kd(m);
      else if (typeof e == "string")
        p = B;
      else
        e: switch (e) {
          case ua:
            return ys(a.children, l, c, t);
          case Ni:
            p = ce, l |= Ct, (l & Dt) !== rt && (l |= cn);
            break;
          case Ai:
            return HD(a, l, c, t);
          case Ae:
            return VD(a, l, c, t);
          case Ue:
            return BD(a, l, c, t);
          case jn:
            return DT(a, l, c, t);
          case Sn:
          case Nt:
          case wn:
          case $r:
          case wt:
          default: {
            if (typeof e == "object" && e !== null)
              switch (e.$$typeof) {
                case ro:
                  p = de;
                  break e;
                case N:
                  p = De;
                  break e;
                case fe:
                  p = ue, m = wE(m);
                  break e;
                case kt:
                  p = Ce;
                  break e;
                case yt:
                  p = _t, m = null;
                  break e;
              }
            var E = "";
            {
              (e === void 0 || typeof e == "object" && e !== null && Object.keys(e).length === 0) && (E += " You likely forgot to export your component from the file it's defined in, or you might have mixed up default and named imports.");
              var R = i ? ht(i) : null;
              R && (E += `

Check the render method of \`` + R + "`.");
            }
            throw new Error("Element type is invalid: expected a string (for built-in components) or a class/function (for composite components) " + ("but got: " + (e == null ? e : typeof e) + "." + E));
          }
        }
      var w = wi(p, a, t, l);
      return w.elementType = e, w.type = m, w.lanes = c, w._debugOwner = i, w;
    }
    function NE(e, t, a) {
      var i = null;
      i = e._owner;
      var l = e.type, c = e.key, p = e.props, m = DE(l, c, p, i, t, a);
      return m._debugSource = e._source, m._debugOwner = e._owner, m;
    }
    function ys(e, t, a, i) {
      var l = wi(j, e, i, t);
      return l.lanes = a, l;
    }
    function HD(e, t, a, i) {
      typeof e.id != "string" && g('Profiler must specify an "id" of type `string` as a prop. Received the type `%s` instead.', typeof e.id);
      var l = wi(q, e, i, t | zt);
      return l.elementType = Ai, l.lanes = a, l.stateNode = {
        effectDuration: 0,
        passiveEffectDuration: 0
      }, l;
    }
    function VD(e, t, a, i) {
      var l = wi(se, e, i, t);
      return l.elementType = Ae, l.lanes = a, l;
    }
    function BD(e, t, a, i) {
      var l = wi(je, e, i, t);
      return l.elementType = Ue, l.lanes = a, l;
    }
    function DT(e, t, a, i) {
      var l = wi(Pe, e, i, t);
      l.elementType = jn, l.lanes = a;
      var c = {
        isHidden: !1
      };
      return l.stateNode = c, l;
    }
    function AE(e, t, a) {
      var i = wi(M, e, null, t);
      return i.lanes = a, i;
    }
    function ID() {
      var e = wi(B, null, null, rt);
      return e.elementType = "DELETED", e;
    }
    function YD(e) {
      var t = wi(ge, null, null, rt);
      return t.stateNode = e, t;
    }
    function ME(e, t, a) {
      var i = e.children !== null ? e.children : [], l = wi(te, i, e.key, t);
      return l.lanes = a, l.stateNode = {
        containerInfo: e.containerInfo,
        pendingChildren: null,
        // Used by persistent updates
        implementation: e.implementation
      }, l;
    }
    function NT(e, t) {
      return e === null && (e = wi(F, null, null, rt)), e.tag = t.tag, e.key = t.key, e.elementType = t.elementType, e.type = t.type, e.stateNode = t.stateNode, e.return = t.return, e.child = t.child, e.sibling = t.sibling, e.index = t.index, e.ref = t.ref, e.pendingProps = t.pendingProps, e.memoizedProps = t.memoizedProps, e.updateQueue = t.updateQueue, e.memoizedState = t.memoizedState, e.dependencies = t.dependencies, e.mode = t.mode, e.flags = t.flags, e.subtreeFlags = t.subtreeFlags, e.deletions = t.deletions, e.lanes = t.lanes, e.childLanes = t.childLanes, e.alternate = t.alternate, e.actualDuration = t.actualDuration, e.actualStartTime = t.actualStartTime, e.selfBaseDuration = t.selfBaseDuration, e.treeBaseDuration = t.treeBaseDuration, e._debugSource = t._debugSource, e._debugOwner = t._debugOwner, e._debugNeedsRemount = t._debugNeedsRemount, e._debugHookTypes = t._debugHookTypes, e;
    }
    function WD(e, t, a, i, l) {
      this.tag = t, this.containerInfo = e, this.pendingChildren = null, this.current = null, this.pingCache = null, this.finishedWork = null, this.timeoutHandle = v0, this.context = null, this.pendingContext = null, this.callbackNode = null, this.callbackPriority = er, this.eventTimes = Mf(oe), this.expirationTimes = Mf(tn), this.pendingLanes = oe, this.suspendedLanes = oe, this.pingedLanes = oe, this.expiredLanes = oe, this.mutableReadLanes = oe, this.finishedLanes = oe, this.entangledLanes = oe, this.entanglements = Mf(oe), this.identifierPrefix = i, this.onRecoverableError = l, this.mutableSourceEagerHydrationData = null, this.effectDuration = 0, this.passiveEffectDuration = 0;
      {
        this.memoizedUpdaters = /* @__PURE__ */ new Set();
        for (var c = this.pendingUpdatersLaneMap = [], p = 0; p < Ep; p++)
          c.push(/* @__PURE__ */ new Set());
      }
      switch (t) {
        case Vm:
          this._debugRootType = a ? "hydrateRoot()" : "createRoot()";
          break;
        case as:
          this._debugRootType = a ? "hydrate()" : "render()";
          break;
      }
    }
    function AT(e, t, a, i, l, c, p, m, E, R) {
      var w = new WD(e, t, a, m, E), V = jD(t, c);
      w.current = V, V.stateNode = w;
      {
        var $ = {
          element: i,
          isDehydrated: a,
          cache: null,
          // not enabled yet
          transitions: null,
          pendingSuspenseBoundaries: null
        };
        V.memoizedState = $;
      }
      return W0(V), w;
    }
    var LE = "18.3.1";
    function GD(e, t, a) {
      var i = arguments.length > 3 && arguments[3] !== void 0 ? arguments[3] : null;
      return _a(i), {
        // This tag allow us to uniquely identify this as a React Portal
        $$typeof: Na,
        key: i == null ? null : "" + i,
        children: e,
        containerInfo: t,
        implementation: a
      };
    }
    var zE, UE;
    zE = !1, UE = {};
    function MT(e) {
      if (!e)
        return Ri;
      var t = Lu(e), a = O_(t);
      if (t.tag === A) {
        var i = t.type;
        if (ol(i))
          return ob(t, i, a);
      }
      return a;
    }
    function QD(e, t) {
      {
        var a = Lu(e);
        if (a === void 0) {
          if (typeof e.render == "function")
            throw new Error("Unable to find node on an unmounted component.");
          var i = Object.keys(e).join(",");
          throw new Error("Argument appears to not be a ReactComponent. Keys: " + i);
        }
        var l = ha(a);
        if (l === null)
          return null;
        if (l.mode & Ct) {
          var c = ht(a) || "Component";
          if (!UE[c]) {
            UE[c] = !0;
            var p = hr;
            try {
              on(l), a.mode & Ct ? g("%s is deprecated in StrictMode. %s was passed an instance of %s which is inside StrictMode. Instead, add a ref directly to the element you want to reference. Learn more about using refs safely here: https://reactjs.org/link/strict-mode-find-node", t, t, c) : g("%s is deprecated in StrictMode. %s was passed an instance of %s which renders StrictMode children. Instead, add a ref directly to the element you want to reference. Learn more about using refs safely here: https://reactjs.org/link/strict-mode-find-node", t, t, c);
            } finally {
              p ? on(p) : zn();
            }
          }
        }
        return l.stateNode;
      }
    }
    function LT(e, t, a, i, l, c, p, m) {
      var E = !1, R = null;
      return AT(e, t, E, R, a, i, l, c, p);
    }
    function zT(e, t, a, i, l, c, p, m, E, R) {
      var w = !0, V = AT(a, i, w, e, l, c, p, m, E);
      V.context = MT(null);
      var $ = V.current, X = Ha(), Z = hs($), ne = iu(X, Z);
      return ne.callback = t ?? null, ls($, ne, Z), tD(V, Z, X), V;
    }
    function jv(e, t, a, i) {
      fp(t, e);
      var l = t.current, c = Ha(), p = hs(l);
      cf(p);
      var m = MT(a);
      t.context === null ? t.context = m : t.pendingContext = m, fa && hr !== null && !zE && (zE = !0, g(`Render methods should be a pure function of props and state; triggering nested component updates from render is not allowed. If necessary, trigger nested updates in componentDidUpdate.

Check the render method of %s.`, ht(hr) || "Unknown"));
      var E = iu(c, p);
      E.payload = {
        element: e
      }, i = i === void 0 ? null : i, i !== null && (typeof i != "function" && g("render(...): Expected the last optional `callback` argument to be a function. Instead received: %s.", i), E.callback = i);
      var R = ls(l, E, p);
      return R !== null && (Ur(R, l, p, c), ry(R, l, p)), p;
    }
    function Wy(e) {
      var t = e.current;
      if (!t.child)
        return null;
      switch (t.child.tag) {
        case B:
          return t.child.stateNode;
        default:
          return t.child.stateNode;
      }
    }
    function qD(e) {
      switch (e.tag) {
        case U: {
          var t = e.stateNode;
          if (Il(t)) {
            var a = Qh(t);
            iD(t, a);
          }
          break;
        }
        case se: {
          su(function() {
            var l = ii(e, ct);
            if (l !== null) {
              var c = Ha();
              Ur(l, e, ct, c);
            }
          });
          var i = ct;
          PE(e, i);
          break;
        }
      }
    }
    function UT(e, t) {
      var a = e.memoizedState;
      a !== null && a.dehydrated !== null && (a.retryLane = xp(a.retryLane, t));
    }
    function PE(e, t) {
      UT(e, t);
      var a = e.alternate;
      a && UT(a, t);
    }
    function KD(e) {
      if (e.tag === se) {
        var t = Bu, a = ii(e, t);
        if (a !== null) {
          var i = Ha();
          Ur(a, e, t, i);
        }
        PE(e, t);
      }
    }
    function XD(e) {
      if (e.tag === se) {
        var t = hs(e), a = ii(e, t);
        if (a !== null) {
          var i = Ha();
          Ur(a, e, t, i);
        }
        PE(e, t);
      }
    }
    function PT(e) {
      var t = Ei(e);
      return t === null ? null : t.stateNode;
    }
    var $T = function(e) {
      return null;
    };
    function JD(e) {
      return $T(e);
    }
    var FT = function(e) {
      return !1;
    };
    function ZD(e) {
      return FT(e);
    }
    var jT = null, HT = null, VT = null, BT = null, IT = null, YT = null, WT = null, GT = null, QT = null;
    {
      var qT = function(e, t, a) {
        var i = t[a], l = bt(e) ? e.slice() : Et({}, e);
        return a + 1 === t.length ? (bt(l) ? l.splice(i, 1) : delete l[i], l) : (l[i] = qT(e[i], t, a + 1), l);
      }, KT = function(e, t) {
        return qT(e, t, 0);
      }, XT = function(e, t, a, i) {
        var l = t[i], c = bt(e) ? e.slice() : Et({}, e);
        if (i + 1 === t.length) {
          var p = a[i];
          c[p] = c[l], bt(c) ? c.splice(l, 1) : delete c[l];
        } else
          c[l] = XT(
            // $FlowFixMe number or string is fine here
            e[l],
            t,
            a,
            i + 1
          );
        return c;
      }, JT = function(e, t, a) {
        if (t.length !== a.length) {
          _("copyWithRename() expects paths of the same length");
          return;
        } else
          for (var i = 0; i < a.length - 1; i++)
            if (t[i] !== a[i]) {
              _("copyWithRename() expects paths to be the same except for the deepest key");
              return;
            }
        return XT(e, t, a, 0);
      }, ZT = function(e, t, a, i) {
        if (a >= t.length)
          return i;
        var l = t[a], c = bt(e) ? e.slice() : Et({}, e);
        return c[l] = ZT(e[l], t, a + 1, i), c;
      }, eR = function(e, t, a) {
        return ZT(e, t, 0, a);
      }, $E = function(e, t) {
        for (var a = e.memoizedState; a !== null && t > 0; )
          a = a.next, t--;
        return a;
      };
      jT = function(e, t, a, i) {
        var l = $E(e, t);
        if (l !== null) {
          var c = eR(l.memoizedState, a, i);
          l.memoizedState = c, l.baseState = c, e.memoizedProps = Et({}, e.memoizedProps);
          var p = ii(e, ct);
          p !== null && Ur(p, e, ct, tn);
        }
      }, HT = function(e, t, a) {
        var i = $E(e, t);
        if (i !== null) {
          var l = KT(i.memoizedState, a);
          i.memoizedState = l, i.baseState = l, e.memoizedProps = Et({}, e.memoizedProps);
          var c = ii(e, ct);
          c !== null && Ur(c, e, ct, tn);
        }
      }, VT = function(e, t, a, i) {
        var l = $E(e, t);
        if (l !== null) {
          var c = JT(l.memoizedState, a, i);
          l.memoizedState = c, l.baseState = c, e.memoizedProps = Et({}, e.memoizedProps);
          var p = ii(e, ct);
          p !== null && Ur(p, e, ct, tn);
        }
      }, BT = function(e, t, a) {
        e.pendingProps = eR(e.memoizedProps, t, a), e.alternate && (e.alternate.pendingProps = e.pendingProps);
        var i = ii(e, ct);
        i !== null && Ur(i, e, ct, tn);
      }, IT = function(e, t) {
        e.pendingProps = KT(e.memoizedProps, t), e.alternate && (e.alternate.pendingProps = e.pendingProps);
        var a = ii(e, ct);
        a !== null && Ur(a, e, ct, tn);
      }, YT = function(e, t, a) {
        e.pendingProps = JT(e.memoizedProps, t, a), e.alternate && (e.alternate.pendingProps = e.pendingProps);
        var i = ii(e, ct);
        i !== null && Ur(i, e, ct, tn);
      }, WT = function(e) {
        var t = ii(e, ct);
        t !== null && Ur(t, e, ct, tn);
      }, GT = function(e) {
        $T = e;
      }, QT = function(e) {
        FT = e;
      };
    }
    function eN(e) {
      var t = ha(e);
      return t === null ? null : t.stateNode;
    }
    function tN(e) {
      return null;
    }
    function nN() {
      return hr;
    }
    function rN(e) {
      var t = e.findFiberByHostInstance, a = y.ReactCurrentDispatcher;
      return cp({
        bundleType: e.bundleType,
        version: e.version,
        rendererPackageName: e.rendererPackageName,
        rendererConfig: e.rendererConfig,
        overrideHookState: jT,
        overrideHookStateDeletePath: HT,
        overrideHookStateRenamePath: VT,
        overrideProps: BT,
        overridePropsDeletePath: IT,
        overridePropsRenamePath: YT,
        setErrorHandler: GT,
        setSuspenseHandler: QT,
        scheduleUpdate: WT,
        currentDispatcherRef: a,
        findHostInstanceByFiber: eN,
        findFiberByHostInstance: t || tN,
        // React Refresh
        findHostInstancesForRefresh: MD,
        scheduleRefresh: ND,
        scheduleRoot: AD,
        setRefreshHandler: DD,
        // Enables DevTools to append owner stacks to error messages in DEV mode.
        getCurrentFiber: nN,
        // Enables DevTools to detect reconciler version rather than renderer version
        // which may not match for third party renderers.
        reconcilerVersion: LE
      });
    }
    var tR = typeof reportError == "function" ? (
      // In modern browsers, reportError will dispatch an error event,
      // emulating an uncaught JavaScript error.
      reportError
    ) : function(e) {
      console.error(e);
    };
    function FE(e) {
      this._internalRoot = e;
    }
    Gy.prototype.render = FE.prototype.render = function(e) {
      var t = this._internalRoot;
      if (t === null)
        throw new Error("Cannot update an unmounted root.");
      {
        typeof arguments[1] == "function" ? g("render(...): does not support the second callback argument. To execute a side effect after rendering, declare it in a component body with useEffect().") : Qy(arguments[1]) ? g("You passed a container to the second argument of root.render(...). You don't need to pass it again since you already passed it to create the root.") : typeof arguments[1] < "u" && g("You passed a second argument to root.render(...) but it only accepts one argument.");
        var a = t.containerInfo;
        if (a.nodeType !== qn) {
          var i = PT(t.current);
          i && i.parentNode !== a && g("render(...): It looks like the React-rendered content of the root container was removed without using React. This is not supported and will cause errors. Instead, call root.unmount() to empty a root's container.");
        }
      }
      jv(e, t, null, null);
    }, Gy.prototype.unmount = FE.prototype.unmount = function() {
      typeof arguments[0] == "function" && g("unmount(...): does not support a callback argument. To execute a side effect after rendering, declare it in a component body with useEffect().");
      var e = this._internalRoot;
      if (e !== null) {
        this._internalRoot = null;
        var t = e.containerInfo;
        pT() && g("Attempted to synchronously unmount a root while React was already rendering. React cannot finish unmounting the root until the current render has completed, which may lead to a race condition."), su(function() {
          jv(null, e, null, null);
        }), tb(t);
      }
    };
    function aN(e, t) {
      if (!Qy(e))
        throw new Error("createRoot(...): Target container is not a DOM element.");
      nR(e);
      var a = !1, i = !1, l = "", c = tR;
      t != null && (t.hydrate ? _("hydrate through createRoot is deprecated. Use ReactDOMClient.hydrateRoot(container, <App />) instead.") : typeof t == "object" && t !== null && t.$$typeof === Tr && g(`You passed a JSX element to createRoot. You probably meant to call root.render instead. Example usage:

  let root = createRoot(domContainer);
  root.render(<App />);`), t.unstable_strictMode === !0 && (a = !0), t.identifierPrefix !== void 0 && (l = t.identifierPrefix), t.onRecoverableError !== void 0 && (c = t.onRecoverableError), t.transitionCallbacks !== void 0 && t.transitionCallbacks);
      var p = LT(e, Vm, null, a, i, l, c);
      zm(p.current, e);
      var m = e.nodeType === qn ? e.parentNode : e;
      return Wp(m), new FE(p);
    }
    function Gy(e) {
      this._internalRoot = e;
    }
    function iN(e) {
      e && im(e);
    }
    Gy.prototype.unstable_scheduleHydration = iN;
    function oN(e, t, a) {
      if (!Qy(e))
        throw new Error("hydrateRoot(...): Target container is not a DOM element.");
      nR(e), t === void 0 && g("Must provide initial children as second argument to hydrateRoot. Example usage: hydrateRoot(domContainer, <App />)");
      var i = a ?? null, l = a != null && a.hydratedSources || null, c = !1, p = !1, m = "", E = tR;
      a != null && (a.unstable_strictMode === !0 && (c = !0), a.identifierPrefix !== void 0 && (m = a.identifierPrefix), a.onRecoverableError !== void 0 && (E = a.onRecoverableError));
      var R = zT(t, null, e, Vm, i, c, p, m, E);
      if (zm(R.current, e), Wp(e), l)
        for (var w = 0; w < l.length; w++) {
          var V = l[w];
          ck(R, V);
        }
      return new Gy(R);
    }
    function Qy(e) {
      return !!(e && (e.nodeType === da || e.nodeType === po || e.nodeType === Os));
    }
    function Hv(e) {
      return !!(e && (e.nodeType === da || e.nodeType === po || e.nodeType === Os || e.nodeType === qn && e.nodeValue === " react-mount-point-unstable "));
    }
    function nR(e) {
      e.nodeType === da && e.tagName && e.tagName.toUpperCase() === "BODY" && g("createRoot(): Creating roots directly with document.body is discouraged, since its children are often manipulated by third-party scripts and browser extensions. This may lead to subtle reconciliation issues. Try using a container element created for your app."), rv(e) && (e._reactRootContainer ? g("You are calling ReactDOMClient.createRoot() on a container that was previously passed to ReactDOM.render(). This is not supported.") : g("You are calling ReactDOMClient.createRoot() on a container that has already been passed to createRoot() before. Instead, call root.render() on the existing root instead if you want to update it."));
    }
    var lN = y.ReactCurrentOwner, rR;
    rR = function(e) {
      if (e._reactRootContainer && e.nodeType !== qn) {
        var t = PT(e._reactRootContainer.current);
        t && t.parentNode !== e && g("render(...): It looks like the React-rendered content of this container was removed without using React. This is not supported and will cause errors. Instead, call ReactDOM.unmountComponentAtNode to empty a container.");
      }
      var a = !!e._reactRootContainer, i = jE(e), l = !!(i && ns(i));
      l && !a && g("render(...): Replacing React-rendered children with a new root component. If you intended to update the children of this node, you should instead have the existing children update their state and render the new components instead of calling ReactDOM.render."), e.nodeType === da && e.tagName && e.tagName.toUpperCase() === "BODY" && g("render(): Rendering components directly into document.body is discouraged, since its children are often manipulated by third-party scripts and browser extensions. This may lead to subtle reconciliation issues. Try rendering into a container element created for your app.");
    };
    function jE(e) {
      return e ? e.nodeType === po ? e.documentElement : e.firstChild : null;
    }
    function aR() {
    }
    function uN(e, t, a, i, l) {
      if (l) {
        if (typeof i == "function") {
          var c = i;
          i = function() {
            var $ = Wy(p);
            c.call($);
          };
        }
        var p = zT(
          t,
          i,
          e,
          as,
          null,
          // hydrationCallbacks
          !1,
          // isStrictMode
          !1,
          // concurrentUpdatesByDefaultOverride,
          "",
          // identifierPrefix
          aR
        );
        e._reactRootContainer = p, zm(p.current, e);
        var m = e.nodeType === qn ? e.parentNode : e;
        return Wp(m), su(), p;
      } else {
        for (var E; E = e.lastChild; )
          e.removeChild(E);
        if (typeof i == "function") {
          var R = i;
          i = function() {
            var $ = Wy(w);
            R.call($);
          };
        }
        var w = LT(
          e,
          as,
          null,
          // hydrationCallbacks
          !1,
          // isStrictMode
          !1,
          // concurrentUpdatesByDefaultOverride,
          "",
          // identifierPrefix
          aR
        );
        e._reactRootContainer = w, zm(w.current, e);
        var V = e.nodeType === qn ? e.parentNode : e;
        return Wp(V), su(function() {
          jv(t, w, a, i);
        }), w;
      }
    }
    function sN(e, t) {
      e !== null && typeof e != "function" && g("%s(...): Expected the last optional `callback` argument to be a function. Instead received: %s.", t, e);
    }
    function qy(e, t, a, i, l) {
      rR(a), sN(l === void 0 ? null : l, "render");
      var c = a._reactRootContainer, p;
      if (!c)
        p = uN(a, t, e, l, i);
      else {
        if (p = c, typeof l == "function") {
          var m = l;
          l = function() {
            var E = Wy(p);
            m.call(E);
          };
        }
        jv(t, p, e, l);
      }
      return Wy(p);
    }
    var iR = !1;
    function cN(e) {
      {
        iR || (iR = !0, g("findDOMNode is deprecated and will be removed in the next major release. Instead, add a ref directly to the element you want to reference. Learn more about using refs safely here: https://reactjs.org/link/strict-mode-find-node"));
        var t = lN.current;
        if (t !== null && t.stateNode !== null) {
          var a = t.stateNode._warnedAboutRefsInRender;
          a || g("%s is accessing findDOMNode inside its render(). render() should be a pure function of props and state. It should never access something that requires stale data from the previous render, such as refs. Move this logic to componentDidMount and componentDidUpdate instead.", $t(t.type) || "A component"), t.stateNode._warnedAboutRefsInRender = !0;
        }
      }
      return e == null ? null : e.nodeType === da ? e : QD(e, "findDOMNode");
    }
    function fN(e, t, a) {
      if (g("ReactDOM.hydrate is no longer supported in React 18. Use hydrateRoot instead. Until you switch to the new API, your app will behave as if it's running React 17. Learn more: https://reactjs.org/link/switch-to-createroot"), !Hv(t))
        throw new Error("Target container is not a DOM element.");
      {
        var i = rv(t) && t._reactRootContainer === void 0;
        i && g("You are calling ReactDOM.hydrate() on a container that was previously passed to ReactDOMClient.createRoot(). This is not supported. Did you mean to call hydrateRoot(container, element)?");
      }
      return qy(null, e, t, !0, a);
    }
    function dN(e, t, a) {
      if (g("ReactDOM.render is no longer supported in React 18. Use createRoot instead. Until you switch to the new API, your app will behave as if it's running React 17. Learn more: https://reactjs.org/link/switch-to-createroot"), !Hv(t))
        throw new Error("Target container is not a DOM element.");
      {
        var i = rv(t) && t._reactRootContainer === void 0;
        i && g("You are calling ReactDOM.render() on a container that was previously passed to ReactDOMClient.createRoot(). This is not supported. Did you mean to call root.render(element)?");
      }
      return qy(null, e, t, !1, a);
    }
    function pN(e, t, a, i) {
      if (g("ReactDOM.unstable_renderSubtreeIntoContainer() is no longer supported in React 18. Consider using a portal instead. Until you switch to the createRoot API, your app will behave as if it's running React 17. Learn more: https://reactjs.org/link/switch-to-createroot"), !Hv(a))
        throw new Error("Target container is not a DOM element.");
      if (e == null || !Ml(e))
        throw new Error("parentComponent must be a valid React Component");
      return qy(e, t, a, !1, i);
    }
    var oR = !1;
    function vN(e) {
      if (oR || (oR = !0, g("unmountComponentAtNode is deprecated and will be removed in the next major release. Switch to the createRoot API. Learn more: https://reactjs.org/link/switch-to-createroot")), !Hv(e))
        throw new Error("unmountComponentAtNode(...): Target container is not a DOM element.");
      {
        var t = rv(e) && e._reactRootContainer === void 0;
        t && g("You are calling ReactDOM.unmountComponentAtNode() on a container that was previously passed to ReactDOMClient.createRoot(). This is not supported. Did you mean to call root.unmount()?");
      }
      if (e._reactRootContainer) {
        {
          var a = jE(e), i = a && !ns(a);
          i && g("unmountComponentAtNode(): The node you're attempting to unmount was rendered by another copy of React.");
        }
        return su(function() {
          qy(null, null, e, !1, function() {
            e._reactRootContainer = null, tb(e);
          });
        }), !0;
      } else {
        {
          var l = jE(e), c = !!(l && ns(l)), p = e.nodeType === da && Hv(e.parentNode) && !!e.parentNode._reactRootContainer;
          c && g("unmountComponentAtNode(): The node you're attempting to unmount was rendered by React and is not a top-level container. %s", p ? "You may have accidentally passed in a React root node instead of its container." : "Instead, have the parent component update its state and rerender in order to remove this component.");
        }
        return !1;
      }
    }
    jg(qD), Dp(KD), Hg(XD), $f(za), tm(Zh), (typeof Map != "function" || // $FlowIssue Flow incorrectly thinks Map has no prototype
    Map.prototype == null || typeof Map.prototype.forEach != "function" || typeof Set != "function" || // $FlowIssue Flow incorrectly thinks Set has no prototype
    Set.prototype == null || typeof Set.prototype.clear != "function" || typeof Set.prototype.forEach != "function") && g("React depends on Map and Set built-in types. Make sure that you load a polyfill in older browsers. https://reactjs.org/link/react-polyfills"), $s(mx), Mh(yE, oD, su);
    function hN(e, t) {
      var a = arguments.length > 2 && arguments[2] !== void 0 ? arguments[2] : null;
      if (!Qy(t))
        throw new Error("Target container is not a DOM element.");
      return GD(e, t, null, a);
    }
    function mN(e, t, a, i) {
      return pN(e, t, a, i);
    }
    var HE = {
      usingClientEntryPoint: !1,
      // Keep in sync with ReactTestUtils.js.
      // This is an array for better minification.
      Events: [ns, id, Um, ep, Du, yE]
    };
    function yN(e, t) {
      return HE.usingClientEntryPoint || g('You are importing createRoot from "react-dom" which is not supported. You should instead import it from "react-dom/client".'), aN(e, t);
    }
    function gN(e, t, a) {
      return HE.usingClientEntryPoint || g('You are importing hydrateRoot from "react-dom" which is not supported. You should instead import it from "react-dom/client".'), oN(e, t, a);
    }
    function SN(e) {
      return pT() && g("flushSync was called from inside a lifecycle method. React cannot flush when React is already rendering. Consider moving this call to a scheduler task or micro task."), su(e);
    }
    var EN = rN({
      findFiberByHostInstance: bc,
      bundleType: 1,
      version: LE,
      rendererPackageName: "react-dom"
    });
    if (!EN && Ht && window.top === window.self && (navigator.userAgent.indexOf("Chrome") > -1 && navigator.userAgent.indexOf("Edge") === -1 || navigator.userAgent.indexOf("Firefox") > -1)) {
      var lR = window.location.protocol;
      /^(https?|file):$/.test(lR) && console.info("%cDownload the React DevTools for a better development experience: https://reactjs.org/link/react-devtools" + (lR === "file:" ? `
You might need to use a local HTTP server (instead of file://): https://reactjs.org/link/react-devtools-faq` : ""), "font-weight:bold");
    }
    ci.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = HE, ci.createPortal = hN, ci.createRoot = yN, ci.findDOMNode = cN, ci.flushSync = SN, ci.hydrate = fN, ci.hydrateRoot = gN, ci.render = dN, ci.unmountComponentAtNode = vN, ci.unstable_batchedUpdates = yE, ci.unstable_renderSubtreeIntoContainer = mN, ci.version = LE, typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u" && typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop == "function" && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop(new Error());
  }(), ci;
}
var nw = {};
function rw() {
  if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function")) {
    if (nw.NODE_ENV !== "production")
      throw new Error("^_^");
    try {
      __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(rw);
    } catch (u) {
      console.error(u);
    }
  }
}
nw.NODE_ENV === "production" ? (rw(), nC.exports = ON()) : nC.exports = DN();
var NN = nC.exports, rC, AN = {}, Xy = NN;
if (AN.NODE_ENV === "production")
  rC = Xy.createRoot, Xy.hydrateRoot;
else {
  var mR = Xy.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  rC = function(u, f) {
    mR.usingClientEntryPoint = !0;
    try {
      return Xy.createRoot(u, f);
    } finally {
      mR.usingClientEntryPoint = !1;
    }
  };
}
let aw = Vt.createContext(
  /** @type {any} */
  null
);
function MN() {
  let u = Vt.useContext(aw);
  if (!u) throw new Error("RenderContext not found");
  return u;
}
function iw() {
  return MN().model;
}
function $c(u) {
  let f = iw(), [v, y] = Vt.useState(f.get(u));
  return Vt.useEffect(() => {
    let S = () => y(f.get(u));
    return f.on(`change:${u}`, S), () => f.off(`change:${u}`, S);
  }, [f, u]), [
    v,
    (S) => {
      f.set(u, S), f.save_changes();
    }
  ];
}
function LN(u) {
  return ({ el: f, model: v, experimental: y }) => {
    let S = rC(f);
    return S.render(
      Vt.createElement(
        Vt.StrictMode,
        null,
        Vt.createElement(
          aw.Provider,
          { value: { model: v, experimental: y } },
          Vt.createElement(u)
        )
      )
    ), () => S.unmount();
  };
}
var aC = { exports: {} }, En = {};
/**
 * @license React
 * react-is.production.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var yR;
function zN() {
  if (yR) return En;
  yR = 1;
  var u = Symbol.for("react.transitional.element"), f = Symbol.for("react.portal"), v = Symbol.for("react.fragment"), y = Symbol.for("react.strict_mode"), S = Symbol.for("react.profiler"), T = Symbol.for("react.consumer"), _ = Symbol.for("react.context"), g = Symbol.for("react.forward_ref"), L = Symbol.for("react.suspense"), z = Symbol.for("react.suspense_list"), A = Symbol.for("react.memo"), F = Symbol.for("react.lazy"), U = Symbol.for("react.offscreen"), te = Symbol.for("react.client.reference");
  function B(M) {
    if (typeof M == "object" && M !== null) {
      var j = M.$$typeof;
      switch (j) {
        case u:
          switch (M = M.type, M) {
            case v:
            case S:
            case y:
            case L:
            case z:
              return M;
            default:
              switch (M = M && M.$$typeof, M) {
                case _:
                case g:
                case F:
                case A:
                  return M;
                case T:
                  return M;
                default:
                  return j;
              }
          }
        case f:
          return j;
      }
    }
  }
  return En.ContextConsumer = T, En.ContextProvider = _, En.Element = u, En.ForwardRef = g, En.Fragment = v, En.Lazy = F, En.Memo = A, En.Portal = f, En.Profiler = S, En.StrictMode = y, En.Suspense = L, En.SuspenseList = z, En.isContextConsumer = function(M) {
    return B(M) === T;
  }, En.isContextProvider = function(M) {
    return B(M) === _;
  }, En.isElement = function(M) {
    return typeof M == "object" && M !== null && M.$$typeof === u;
  }, En.isForwardRef = function(M) {
    return B(M) === g;
  }, En.isFragment = function(M) {
    return B(M) === v;
  }, En.isLazy = function(M) {
    return B(M) === F;
  }, En.isMemo = function(M) {
    return B(M) === A;
  }, En.isPortal = function(M) {
    return B(M) === f;
  }, En.isProfiler = function(M) {
    return B(M) === S;
  }, En.isStrictMode = function(M) {
    return B(M) === y;
  }, En.isSuspense = function(M) {
    return B(M) === L;
  }, En.isSuspenseList = function(M) {
    return B(M) === z;
  }, En.isValidElementType = function(M) {
    return typeof M == "string" || typeof M == "function" || M === v || M === S || M === y || M === L || M === z || M === U || typeof M == "object" && M !== null && (M.$$typeof === F || M.$$typeof === A || M.$$typeof === _ || M.$$typeof === T || M.$$typeof === g || M.$$typeof === te || M.getModuleId !== void 0);
  }, En.typeOf = B, En;
}
var Cn = {}, gR;
function UN() {
  if (gR) return Cn;
  gR = 1;
  var u = {};
  /**
   * @license React
   * react-is.development.js
   *
   * Copyright (c) Meta Platforms, Inc. and affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   */
  return u.NODE_ENV !== "production" && function() {
    function f(j) {
      if (typeof j == "object" && j !== null) {
        var ce = j.$$typeof;
        switch (ce) {
          case v:
            switch (j = j.type, j) {
              case S:
              case _:
              case T:
              case A:
              case F:
                return j;
              default:
                switch (j = j && j.$$typeof, j) {
                  case L:
                  case z:
                  case te:
                  case U:
                    return j;
                  case g:
                    return j;
                  default:
                    return ce;
                }
            }
          case y:
            return ce;
        }
      }
    }
    var v = Symbol.for("react.transitional.element"), y = Symbol.for("react.portal"), S = Symbol.for("react.fragment"), T = Symbol.for("react.strict_mode"), _ = Symbol.for("react.profiler"), g = Symbol.for("react.consumer"), L = Symbol.for("react.context"), z = Symbol.for("react.forward_ref"), A = Symbol.for("react.suspense"), F = Symbol.for("react.suspense_list"), U = Symbol.for("react.memo"), te = Symbol.for("react.lazy"), B = Symbol.for("react.offscreen"), M = Symbol.for("react.client.reference");
    Cn.ContextConsumer = g, Cn.ContextProvider = L, Cn.Element = v, Cn.ForwardRef = z, Cn.Fragment = S, Cn.Lazy = te, Cn.Memo = U, Cn.Portal = y, Cn.Profiler = _, Cn.StrictMode = T, Cn.Suspense = A, Cn.SuspenseList = F, Cn.isContextConsumer = function(j) {
      return f(j) === g;
    }, Cn.isContextProvider = function(j) {
      return f(j) === L;
    }, Cn.isElement = function(j) {
      return typeof j == "object" && j !== null && j.$$typeof === v;
    }, Cn.isForwardRef = function(j) {
      return f(j) === z;
    }, Cn.isFragment = function(j) {
      return f(j) === S;
    }, Cn.isLazy = function(j) {
      return f(j) === te;
    }, Cn.isMemo = function(j) {
      return f(j) === U;
    }, Cn.isPortal = function(j) {
      return f(j) === y;
    }, Cn.isProfiler = function(j) {
      return f(j) === _;
    }, Cn.isStrictMode = function(j) {
      return f(j) === T;
    }, Cn.isSuspense = function(j) {
      return f(j) === A;
    }, Cn.isSuspenseList = function(j) {
      return f(j) === F;
    }, Cn.isValidElementType = function(j) {
      return typeof j == "string" || typeof j == "function" || j === S || j === _ || j === T || j === A || j === F || j === B || typeof j == "object" && j !== null && (j.$$typeof === te || j.$$typeof === U || j.$$typeof === L || j.$$typeof === g || j.$$typeof === z || j.$$typeof === M || j.getModuleId !== void 0);
    }, Cn.typeOf = f;
  }(), Cn;
}
var PN = {};
PN.NODE_ENV === "production" ? aC.exports = zN() : aC.exports = UN();
var lg = aC.exports;
function pu(u) {
  if (typeof u != "object" || u === null)
    return !1;
  const f = Object.getPrototypeOf(u);
  return (f === null || f === Object.prototype || Object.getPrototypeOf(f) === null) && !(Symbol.toStringTag in u) && !(Symbol.iterator in u);
}
function ow(u) {
  if (/* @__PURE__ */ Vt.isValidElement(u) || lg.isValidElementType(u) || !pu(u))
    return u;
  const f = {};
  return Object.keys(u).forEach((v) => {
    f[v] = ow(u[v]);
  }), f;
}
function ki(u, f, v = {
  clone: !0
}) {
  const y = v.clone ? {
    ...u
  } : u;
  return pu(u) && pu(f) && Object.keys(f).forEach((S) => {
    /* @__PURE__ */ Vt.isValidElement(f[S]) || lg.isValidElementType(f[S]) ? y[S] = f[S] : pu(f[S]) && // Avoid prototype pollution
    Object.prototype.hasOwnProperty.call(u, S) && pu(u[S]) ? y[S] = ki(u[S], f[S], v) : v.clone ? y[S] = pu(f[S]) ? ow(f[S]) : f[S] : y[S] = f[S];
  }), y;
}
var iC = { exports: {} }, Jy = { exports: {} }, pn = {};
/** @license React v16.13.1
 * react-is.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var SR;
function $N() {
  if (SR) return pn;
  SR = 1;
  var u = typeof Symbol == "function" && Symbol.for, f = u ? Symbol.for("react.element") : 60103, v = u ? Symbol.for("react.portal") : 60106, y = u ? Symbol.for("react.fragment") : 60107, S = u ? Symbol.for("react.strict_mode") : 60108, T = u ? Symbol.for("react.profiler") : 60114, _ = u ? Symbol.for("react.provider") : 60109, g = u ? Symbol.for("react.context") : 60110, L = u ? Symbol.for("react.async_mode") : 60111, z = u ? Symbol.for("react.concurrent_mode") : 60111, A = u ? Symbol.for("react.forward_ref") : 60112, F = u ? Symbol.for("react.suspense") : 60113, U = u ? Symbol.for("react.suspense_list") : 60120, te = u ? Symbol.for("react.memo") : 60115, B = u ? Symbol.for("react.lazy") : 60116, M = u ? Symbol.for("react.block") : 60121, j = u ? Symbol.for("react.fundamental") : 60117, ce = u ? Symbol.for("react.responder") : 60118, De = u ? Symbol.for("react.scope") : 60119;
  function de(q) {
    if (typeof q == "object" && q !== null) {
      var se = q.$$typeof;
      switch (se) {
        case f:
          switch (q = q.type, q) {
            case L:
            case z:
            case y:
            case T:
            case S:
            case F:
              return q;
            default:
              switch (q = q && q.$$typeof, q) {
                case g:
                case A:
                case B:
                case te:
                case _:
                  return q;
                default:
                  return se;
              }
          }
        case v:
          return se;
      }
    }
  }
  function ue(q) {
    return de(q) === z;
  }
  return pn.AsyncMode = L, pn.ConcurrentMode = z, pn.ContextConsumer = g, pn.ContextProvider = _, pn.Element = f, pn.ForwardRef = A, pn.Fragment = y, pn.Lazy = B, pn.Memo = te, pn.Portal = v, pn.Profiler = T, pn.StrictMode = S, pn.Suspense = F, pn.isAsyncMode = function(q) {
    return ue(q) || de(q) === L;
  }, pn.isConcurrentMode = ue, pn.isContextConsumer = function(q) {
    return de(q) === g;
  }, pn.isContextProvider = function(q) {
    return de(q) === _;
  }, pn.isElement = function(q) {
    return typeof q == "object" && q !== null && q.$$typeof === f;
  }, pn.isForwardRef = function(q) {
    return de(q) === A;
  }, pn.isFragment = function(q) {
    return de(q) === y;
  }, pn.isLazy = function(q) {
    return de(q) === B;
  }, pn.isMemo = function(q) {
    return de(q) === te;
  }, pn.isPortal = function(q) {
    return de(q) === v;
  }, pn.isProfiler = function(q) {
    return de(q) === T;
  }, pn.isStrictMode = function(q) {
    return de(q) === S;
  }, pn.isSuspense = function(q) {
    return de(q) === F;
  }, pn.isValidElementType = function(q) {
    return typeof q == "string" || typeof q == "function" || q === y || q === z || q === T || q === S || q === F || q === U || typeof q == "object" && q !== null && (q.$$typeof === B || q.$$typeof === te || q.$$typeof === _ || q.$$typeof === g || q.$$typeof === A || q.$$typeof === j || q.$$typeof === ce || q.$$typeof === De || q.$$typeof === M);
  }, pn.typeOf = de, pn;
}
var vn = {}, ER;
function FN() {
  if (ER) return vn;
  ER = 1;
  var u = {};
  /** @license React v16.13.1
   * react-is.development.js
   *
   * Copyright (c) Facebook, Inc. and its affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   */
  return u.NODE_ENV !== "production" && function() {
    var f = typeof Symbol == "function" && Symbol.for, v = f ? Symbol.for("react.element") : 60103, y = f ? Symbol.for("react.portal") : 60106, S = f ? Symbol.for("react.fragment") : 60107, T = f ? Symbol.for("react.strict_mode") : 60108, _ = f ? Symbol.for("react.profiler") : 60114, g = f ? Symbol.for("react.provider") : 60109, L = f ? Symbol.for("react.context") : 60110, z = f ? Symbol.for("react.async_mode") : 60111, A = f ? Symbol.for("react.concurrent_mode") : 60111, F = f ? Symbol.for("react.forward_ref") : 60112, U = f ? Symbol.for("react.suspense") : 60113, te = f ? Symbol.for("react.suspense_list") : 60120, B = f ? Symbol.for("react.memo") : 60115, M = f ? Symbol.for("react.lazy") : 60116, j = f ? Symbol.for("react.block") : 60121, ce = f ? Symbol.for("react.fundamental") : 60117, De = f ? Symbol.for("react.responder") : 60118, de = f ? Symbol.for("react.scope") : 60119;
    function ue(Te) {
      return typeof Te == "string" || typeof Te == "function" || // Note: its typeof might be other than 'symbol' or 'number' if it's a polyfill.
      Te === S || Te === A || Te === _ || Te === T || Te === U || Te === te || typeof Te == "object" && Te !== null && (Te.$$typeof === M || Te.$$typeof === B || Te.$$typeof === g || Te.$$typeof === L || Te.$$typeof === F || Te.$$typeof === ce || Te.$$typeof === De || Te.$$typeof === de || Te.$$typeof === j);
    }
    function q(Te) {
      if (typeof Te == "object" && Te !== null) {
        var Wt = Te.$$typeof;
        switch (Wt) {
          case v:
            var Fn = Te.type;
            switch (Fn) {
              case z:
              case A:
              case S:
              case _:
              case T:
              case U:
                return Fn;
              default:
                var Ln = Fn && Fn.$$typeof;
                switch (Ln) {
                  case L:
                  case F:
                  case M:
                  case B:
                  case g:
                    return Ln;
                  default:
                    return Wt;
                }
            }
          case y:
            return Wt;
        }
      }
    }
    var se = z, Ce = A, Ge = L, _t = g, x = v, ge = F, je = S, Qe = M, Pe = B, pt = y, vt = _, ot = T, ie = U, Ie = !1;
    function ke(Te) {
      return Ie || (Ie = !0, console.warn("The ReactIs.isAsyncMode() alias has been deprecated, and will be removed in React 17+. Update your code to use ReactIs.isConcurrentMode() instead. It has the exact same API.")), k(Te) || q(Te) === z;
    }
    function k(Te) {
      return q(Te) === A;
    }
    function I(Te) {
      return q(Te) === L;
    }
    function ye(Te) {
      return q(Te) === g;
    }
    function Re(Te) {
      return typeof Te == "object" && Te !== null && Te.$$typeof === v;
    }
    function be(Te) {
      return q(Te) === F;
    }
    function Le(Te) {
      return q(Te) === S;
    }
    function ze(Te) {
      return q(Te) === M;
    }
    function we(Te) {
      return q(Te) === B;
    }
    function Ye(Te) {
      return q(Te) === y;
    }
    function et(Te) {
      return q(Te) === _;
    }
    function ut(Te) {
      return q(Te) === T;
    }
    function Ht(Te) {
      return q(Te) === U;
    }
    vn.AsyncMode = se, vn.ConcurrentMode = Ce, vn.ContextConsumer = Ge, vn.ContextProvider = _t, vn.Element = x, vn.ForwardRef = ge, vn.Fragment = je, vn.Lazy = Qe, vn.Memo = Pe, vn.Portal = pt, vn.Profiler = vt, vn.StrictMode = ot, vn.Suspense = ie, vn.isAsyncMode = ke, vn.isConcurrentMode = k, vn.isContextConsumer = I, vn.isContextProvider = ye, vn.isElement = Re, vn.isForwardRef = be, vn.isFragment = Le, vn.isLazy = ze, vn.isMemo = we, vn.isPortal = Ye, vn.isProfiler = et, vn.isStrictMode = ut, vn.isSuspense = Ht, vn.isValidElementType = ue, vn.typeOf = q;
  }(), vn;
}
var CR;
function lw() {
  if (CR) return Jy.exports;
  CR = 1;
  var u = {};
  return u.NODE_ENV === "production" ? Jy.exports = $N() : Jy.exports = FN(), Jy.exports;
}
/*
object-assign
(c) Sindre Sorhus
@license MIT
*/
var IE, bR;
function jN() {
  if (bR) return IE;
  bR = 1;
  var u = Object.getOwnPropertySymbols, f = Object.prototype.hasOwnProperty, v = Object.prototype.propertyIsEnumerable;
  function y(T) {
    if (T == null)
      throw new TypeError("Object.assign cannot be called with null or undefined");
    return Object(T);
  }
  function S() {
    try {
      if (!Object.assign)
        return !1;
      var T = new String("abc");
      if (T[5] = "de", Object.getOwnPropertyNames(T)[0] === "5")
        return !1;
      for (var _ = {}, g = 0; g < 10; g++)
        _["_" + String.fromCharCode(g)] = g;
      var L = Object.getOwnPropertyNames(_).map(function(A) {
        return _[A];
      });
      if (L.join("") !== "0123456789")
        return !1;
      var z = {};
      return "abcdefghijklmnopqrst".split("").forEach(function(A) {
        z[A] = A;
      }), Object.keys(Object.assign({}, z)).join("") === "abcdefghijklmnopqrst";
    } catch {
      return !1;
    }
  }
  return IE = S() ? Object.assign : function(T, _) {
    for (var g, L = y(T), z, A = 1; A < arguments.length; A++) {
      g = Object(arguments[A]);
      for (var F in g)
        f.call(g, F) && (L[F] = g[F]);
      if (u) {
        z = u(g);
        for (var U = 0; U < z.length; U++)
          v.call(g, z[U]) && (L[z[U]] = g[z[U]]);
      }
    }
    return L;
  }, IE;
}
var YE, TR;
function vC() {
  if (TR) return YE;
  TR = 1;
  var u = "SECRET_DO_NOT_PASS_THIS_OR_YOU_WILL_BE_FIRED";
  return YE = u, YE;
}
var WE, RR;
function uw() {
  return RR || (RR = 1, WE = Function.call.bind(Object.prototype.hasOwnProperty)), WE;
}
var GE, wR;
function HN() {
  if (wR) return GE;
  wR = 1;
  var u = {}, f = function() {
  };
  if (u.NODE_ENV !== "production") {
    var v = vC(), y = {}, S = uw();
    f = function(_) {
      var g = "Warning: " + _;
      typeof console < "u" && console.error(g);
      try {
        throw new Error(g);
      } catch {
      }
    };
  }
  function T(_, g, L, z, A) {
    if (u.NODE_ENV !== "production") {
      for (var F in _)
        if (S(_, F)) {
          var U;
          try {
            if (typeof _[F] != "function") {
              var te = Error(
                (z || "React class") + ": " + L + " type `" + F + "` is invalid; it must be a function, usually from the `prop-types` package, but received `" + typeof _[F] + "`.This often happens because of typos such as `PropTypes.function` instead of `PropTypes.func`."
              );
              throw te.name = "Invariant Violation", te;
            }
            U = _[F](g, F, z, L, null, v);
          } catch (M) {
            U = M;
          }
          if (U && !(U instanceof Error) && f(
            (z || "React class") + ": type specification of " + L + " `" + F + "` is invalid; the type checker function must return `null` or an `Error` but returned a " + typeof U + ". You may have forgotten to pass an argument to the type checker creator (arrayOf, instanceOf, objectOf, oneOf, oneOfType, and shape all require an argument)."
          ), U instanceof Error && !(U.message in y)) {
            y[U.message] = !0;
            var B = A ? A() : "";
            f(
              "Failed " + L + " type: " + U.message + (B ?? "")
            );
          }
        }
    }
  }
  return T.resetWarningCache = function() {
    u.NODE_ENV !== "production" && (y = {});
  }, GE = T, GE;
}
var QE, xR;
function VN() {
  if (xR) return QE;
  xR = 1;
  var u = {}, f = lw(), v = jN(), y = vC(), S = uw(), T = HN(), _ = function() {
  };
  u.NODE_ENV !== "production" && (_ = function(L) {
    var z = "Warning: " + L;
    typeof console < "u" && console.error(z);
    try {
      throw new Error(z);
    } catch {
    }
  });
  function g() {
    return null;
  }
  return QE = function(L, z) {
    var A = typeof Symbol == "function" && Symbol.iterator, F = "@@iterator";
    function U(k) {
      var I = k && (A && k[A] || k[F]);
      if (typeof I == "function")
        return I;
    }
    var te = "<<anonymous>>", B = {
      array: De("array"),
      bigint: De("bigint"),
      bool: De("boolean"),
      func: De("function"),
      number: De("number"),
      object: De("object"),
      string: De("string"),
      symbol: De("symbol"),
      any: de(),
      arrayOf: ue,
      element: q(),
      elementType: se(),
      instanceOf: Ce,
      node: ge(),
      objectOf: _t,
      oneOf: Ge,
      oneOfType: x,
      shape: Qe,
      exact: Pe
    };
    function M(k, I) {
      return k === I ? k !== 0 || 1 / k === 1 / I : k !== k && I !== I;
    }
    function j(k, I) {
      this.message = k, this.data = I && typeof I == "object" ? I : {}, this.stack = "";
    }
    j.prototype = Error.prototype;
    function ce(k) {
      if (u.NODE_ENV !== "production")
        var I = {}, ye = 0;
      function Re(Le, ze, we, Ye, et, ut, Ht) {
        if (Ye = Ye || te, ut = ut || we, Ht !== y) {
          if (z) {
            var Te = new Error(
              "Calling PropTypes validators directly is not supported by the `prop-types` package. Use `PropTypes.checkPropTypes()` to call them. Read more at http://fb.me/use-check-prop-types"
            );
            throw Te.name = "Invariant Violation", Te;
          } else if (u.NODE_ENV !== "production" && typeof console < "u") {
            var Wt = Ye + ":" + we;
            !I[Wt] && // Avoid spamming the console because they are often not actionable except for lib authors
            ye < 3 && (_(
              "You are manually calling a React.PropTypes validation function for the `" + ut + "` prop on `" + Ye + "`. This is deprecated and will throw in the standalone `prop-types` package. You may be seeing this warning due to a third-party PropTypes library. See https://fb.me/react-warning-dont-call-proptypes for details."
            ), I[Wt] = !0, ye++);
          }
        }
        return ze[we] == null ? Le ? ze[we] === null ? new j("The " + et + " `" + ut + "` is marked as required " + ("in `" + Ye + "`, but its value is `null`.")) : new j("The " + et + " `" + ut + "` is marked as required in " + ("`" + Ye + "`, but its value is `undefined`.")) : null : k(ze, we, Ye, et, ut);
      }
      var be = Re.bind(null, !1);
      return be.isRequired = Re.bind(null, !0), be;
    }
    function De(k) {
      function I(ye, Re, be, Le, ze, we) {
        var Ye = ye[Re], et = ot(Ye);
        if (et !== k) {
          var ut = ie(Ye);
          return new j(
            "Invalid " + Le + " `" + ze + "` of type " + ("`" + ut + "` supplied to `" + be + "`, expected ") + ("`" + k + "`."),
            { expectedType: k }
          );
        }
        return null;
      }
      return ce(I);
    }
    function de() {
      return ce(g);
    }
    function ue(k) {
      function I(ye, Re, be, Le, ze) {
        if (typeof k != "function")
          return new j("Property `" + ze + "` of component `" + be + "` has invalid PropType notation inside arrayOf.");
        var we = ye[Re];
        if (!Array.isArray(we)) {
          var Ye = ot(we);
          return new j("Invalid " + Le + " `" + ze + "` of type " + ("`" + Ye + "` supplied to `" + be + "`, expected an array."));
        }
        for (var et = 0; et < we.length; et++) {
          var ut = k(we, et, be, Le, ze + "[" + et + "]", y);
          if (ut instanceof Error)
            return ut;
        }
        return null;
      }
      return ce(I);
    }
    function q() {
      function k(I, ye, Re, be, Le) {
        var ze = I[ye];
        if (!L(ze)) {
          var we = ot(ze);
          return new j("Invalid " + be + " `" + Le + "` of type " + ("`" + we + "` supplied to `" + Re + "`, expected a single ReactElement."));
        }
        return null;
      }
      return ce(k);
    }
    function se() {
      function k(I, ye, Re, be, Le) {
        var ze = I[ye];
        if (!f.isValidElementType(ze)) {
          var we = ot(ze);
          return new j("Invalid " + be + " `" + Le + "` of type " + ("`" + we + "` supplied to `" + Re + "`, expected a single ReactElement type."));
        }
        return null;
      }
      return ce(k);
    }
    function Ce(k) {
      function I(ye, Re, be, Le, ze) {
        if (!(ye[Re] instanceof k)) {
          var we = k.name || te, Ye = ke(ye[Re]);
          return new j("Invalid " + Le + " `" + ze + "` of type " + ("`" + Ye + "` supplied to `" + be + "`, expected ") + ("instance of `" + we + "`."));
        }
        return null;
      }
      return ce(I);
    }
    function Ge(k) {
      if (!Array.isArray(k))
        return u.NODE_ENV !== "production" && (arguments.length > 1 ? _(
          "Invalid arguments supplied to oneOf, expected an array, got " + arguments.length + " arguments. A common mistake is to write oneOf(x, y, z) instead of oneOf([x, y, z])."
        ) : _("Invalid argument supplied to oneOf, expected an array.")), g;
      function I(ye, Re, be, Le, ze) {
        for (var we = ye[Re], Ye = 0; Ye < k.length; Ye++)
          if (M(we, k[Ye]))
            return null;
        var et = JSON.stringify(k, function(Ht, Te) {
          var Wt = ie(Te);
          return Wt === "symbol" ? String(Te) : Te;
        });
        return new j("Invalid " + Le + " `" + ze + "` of value `" + String(we) + "` " + ("supplied to `" + be + "`, expected one of " + et + "."));
      }
      return ce(I);
    }
    function _t(k) {
      function I(ye, Re, be, Le, ze) {
        if (typeof k != "function")
          return new j("Property `" + ze + "` of component `" + be + "` has invalid PropType notation inside objectOf.");
        var we = ye[Re], Ye = ot(we);
        if (Ye !== "object")
          return new j("Invalid " + Le + " `" + ze + "` of type " + ("`" + Ye + "` supplied to `" + be + "`, expected an object."));
        for (var et in we)
          if (S(we, et)) {
            var ut = k(we, et, be, Le, ze + "." + et, y);
            if (ut instanceof Error)
              return ut;
          }
        return null;
      }
      return ce(I);
    }
    function x(k) {
      if (!Array.isArray(k))
        return u.NODE_ENV !== "production" && _("Invalid argument supplied to oneOfType, expected an instance of array."), g;
      for (var I = 0; I < k.length; I++) {
        var ye = k[I];
        if (typeof ye != "function")
          return _(
            "Invalid argument supplied to oneOfType. Expected an array of check functions, but received " + Ie(ye) + " at index " + I + "."
          ), g;
      }
      function Re(be, Le, ze, we, Ye) {
        for (var et = [], ut = 0; ut < k.length; ut++) {
          var Ht = k[ut], Te = Ht(be, Le, ze, we, Ye, y);
          if (Te == null)
            return null;
          Te.data && S(Te.data, "expectedType") && et.push(Te.data.expectedType);
        }
        var Wt = et.length > 0 ? ", expected one of type [" + et.join(", ") + "]" : "";
        return new j("Invalid " + we + " `" + Ye + "` supplied to " + ("`" + ze + "`" + Wt + "."));
      }
      return ce(Re);
    }
    function ge() {
      function k(I, ye, Re, be, Le) {
        return pt(I[ye]) ? null : new j("Invalid " + be + " `" + Le + "` supplied to " + ("`" + Re + "`, expected a ReactNode."));
      }
      return ce(k);
    }
    function je(k, I, ye, Re, be) {
      return new j(
        (k || "React class") + ": " + I + " type `" + ye + "." + Re + "` is invalid; it must be a function, usually from the `prop-types` package, but received `" + be + "`."
      );
    }
    function Qe(k) {
      function I(ye, Re, be, Le, ze) {
        var we = ye[Re], Ye = ot(we);
        if (Ye !== "object")
          return new j("Invalid " + Le + " `" + ze + "` of type `" + Ye + "` " + ("supplied to `" + be + "`, expected `object`."));
        for (var et in k) {
          var ut = k[et];
          if (typeof ut != "function")
            return je(be, Le, ze, et, ie(ut));
          var Ht = ut(we, et, be, Le, ze + "." + et, y);
          if (Ht)
            return Ht;
        }
        return null;
      }
      return ce(I);
    }
    function Pe(k) {
      function I(ye, Re, be, Le, ze) {
        var we = ye[Re], Ye = ot(we);
        if (Ye !== "object")
          return new j("Invalid " + Le + " `" + ze + "` of type `" + Ye + "` " + ("supplied to `" + be + "`, expected `object`."));
        var et = v({}, ye[Re], k);
        for (var ut in et) {
          var Ht = k[ut];
          if (S(k, ut) && typeof Ht != "function")
            return je(be, Le, ze, ut, ie(Ht));
          if (!Ht)
            return new j(
              "Invalid " + Le + " `" + ze + "` key `" + ut + "` supplied to `" + be + "`.\nBad object: " + JSON.stringify(ye[Re], null, "  ") + `
Valid keys: ` + JSON.stringify(Object.keys(k), null, "  ")
            );
          var Te = Ht(we, ut, be, Le, ze + "." + ut, y);
          if (Te)
            return Te;
        }
        return null;
      }
      return ce(I);
    }
    function pt(k) {
      switch (typeof k) {
        case "number":
        case "string":
        case "undefined":
          return !0;
        case "boolean":
          return !k;
        case "object":
          if (Array.isArray(k))
            return k.every(pt);
          if (k === null || L(k))
            return !0;
          var I = U(k);
          if (I) {
            var ye = I.call(k), Re;
            if (I !== k.entries) {
              for (; !(Re = ye.next()).done; )
                if (!pt(Re.value))
                  return !1;
            } else
              for (; !(Re = ye.next()).done; ) {
                var be = Re.value;
                if (be && !pt(be[1]))
                  return !1;
              }
          } else
            return !1;
          return !0;
        default:
          return !1;
      }
    }
    function vt(k, I) {
      return k === "symbol" ? !0 : I ? I["@@toStringTag"] === "Symbol" || typeof Symbol == "function" && I instanceof Symbol : !1;
    }
    function ot(k) {
      var I = typeof k;
      return Array.isArray(k) ? "array" : k instanceof RegExp ? "object" : vt(I, k) ? "symbol" : I;
    }
    function ie(k) {
      if (typeof k > "u" || k === null)
        return "" + k;
      var I = ot(k);
      if (I === "object") {
        if (k instanceof Date)
          return "date";
        if (k instanceof RegExp)
          return "regexp";
      }
      return I;
    }
    function Ie(k) {
      var I = ie(k);
      switch (I) {
        case "array":
        case "object":
          return "an " + I;
        case "boolean":
        case "date":
        case "regexp":
          return "a " + I;
        default:
          return I;
      }
    }
    function ke(k) {
      return !k.constructor || !k.constructor.name ? te : k.constructor.name;
    }
    return B.checkPropTypes = T, B.resetWarningCache = T.resetWarningCache, B.PropTypes = B, B;
  }, QE;
}
var qE, _R;
function BN() {
  if (_R) return qE;
  _R = 1;
  var u = vC();
  function f() {
  }
  function v() {
  }
  return v.resetWarningCache = f, qE = function() {
    function y(_, g, L, z, A, F) {
      if (F !== u) {
        var U = new Error(
          "Calling PropTypes validators directly is not supported by the `prop-types` package. Use PropTypes.checkPropTypes() to call them. Read more at http://fb.me/use-check-prop-types"
        );
        throw U.name = "Invariant Violation", U;
      }
    }
    y.isRequired = y;
    function S() {
      return y;
    }
    var T = {
      array: y,
      bigint: y,
      bool: y,
      func: y,
      number: y,
      object: y,
      string: y,
      symbol: y,
      any: y,
      arrayOf: S,
      element: y,
      elementType: y,
      instanceOf: S,
      node: y,
      objectOf: S,
      oneOf: S,
      oneOfType: S,
      shape: S,
      exact: S,
      checkPropTypes: v,
      resetWarningCache: f
    };
    return T.PropTypes = T, T;
  }, qE;
}
var IN = {};
if (IN.NODE_ENV !== "production") {
  var YN = lw(), WN = !0;
  iC.exports = VN()(YN.isElement, WN);
} else
  iC.exports = BN()();
var GN = iC.exports;
const Zt = /* @__PURE__ */ ew(GN);
function gs(u, ...f) {
  const v = new URL(`https://mui.com/production-error/?code=${u}`);
  return f.forEach((y) => v.searchParams.append("args[]", y)), `Minified MUI error #${u}; visit ${v} for the full message.`;
}
function sw(u, f = "") {
  return u.displayName || u.name || f;
}
function kR(u, f, v) {
  const y = sw(f);
  return u.displayName || (y !== "" ? `${v}(${y})` : v);
}
function QN(u) {
  if (u != null) {
    if (typeof u == "string")
      return u;
    if (typeof u == "function")
      return sw(u, "Component");
    if (typeof u == "object")
      switch (u.$$typeof) {
        case lg.ForwardRef:
          return kR(u, u.render, "ForwardRef");
        case lg.Memo:
          return kR(u, u.type, "memo");
        default:
          return;
      }
  }
}
var qN = {};
function Fc(u) {
  if (typeof u != "string")
    throw new Error(qN.NODE_ENV !== "production" ? "MUI: `capitalize(string)` expects a string argument." : gs(7));
  return u.charAt(0).toUpperCase() + u.slice(1);
}
function oC(u, f) {
  const v = {
    ...f
  };
  for (const y in u)
    if (Object.prototype.hasOwnProperty.call(u, y)) {
      const S = y;
      if (S === "components" || S === "slots")
        v[S] = {
          ...u[S],
          ...v[S]
        };
      else if (S === "componentsProps" || S === "slotProps") {
        const T = u[S], _ = f[S];
        if (!_)
          v[S] = T || {};
        else if (!T)
          v[S] = _;
        else {
          v[S] = {
            ..._
          };
          for (const g in T)
            if (Object.prototype.hasOwnProperty.call(T, g)) {
              const L = g;
              v[S][L] = oC(T[L], _[L]);
            }
        }
      } else v[S] === void 0 && (v[S] = u[S]);
    }
  return v;
}
function KN(u, f, v = void 0) {
  const y = {};
  for (const S in u) {
    const T = u[S];
    let _ = "", g = !0;
    for (let L = 0; L < T.length; L += 1) {
      const z = T[L];
      z && (_ += (g === !0 ? "" : " ") + f(z), g = !1, v && v[z] && (_ += " " + v[z]));
    }
    y[S] = _;
  }
  return y;
}
const OR = (u) => u, XN = () => {
  let u = OR;
  return {
    configure(f) {
      u = f;
    },
    generate(f) {
      return u(f);
    },
    reset() {
      u = OR;
    }
  };
}, JN = XN(), ZN = {
  active: "active",
  checked: "checked",
  completed: "completed",
  disabled: "disabled",
  error: "error",
  expanded: "expanded",
  focused: "focused",
  focusVisible: "focusVisible",
  open: "open",
  readOnly: "readOnly",
  required: "required",
  selected: "selected"
};
function hC(u, f, v = "Mui") {
  const y = ZN[f];
  return y ? `${v}-${y}` : `${JN.generate(u)}-${f}`;
}
function eA(u, f, v = "Mui") {
  const y = {};
  return f.forEach((S) => {
    y[S] = hC(u, S, v);
  }), y;
}
function tA(u, f = Number.MIN_SAFE_INTEGER, v = Number.MAX_SAFE_INTEGER) {
  return Math.max(f, Math.min(u, v));
}
function cw(u) {
  var f, v, y = "";
  if (typeof u == "string" || typeof u == "number") y += u;
  else if (typeof u == "object") if (Array.isArray(u)) {
    var S = u.length;
    for (f = 0; f < S; f++) u[f] && (v = cw(u[f])) && (y && (y += " "), y += v);
  } else for (v in u) u[v] && (y && (y += " "), y += v);
  return y;
}
function nA() {
  for (var u, f, v = 0, y = "", S = arguments.length; v < S; v++) (u = arguments[v]) && (f = cw(u)) && (y && (y += " "), y += f);
  return y;
}
function Kv(u, f) {
  return f ? ki(u, f, {
    clone: !1
    // No need to clone deep, it's way faster.
  }) : u;
}
var rA = {};
const Es = rA.NODE_ENV !== "production" ? Zt.oneOfType([Zt.number, Zt.string, Zt.object, Zt.array]) : {};
var DR = {};
function aA(u, f) {
  if (!u.containerQueries)
    return f;
  const v = Object.keys(f).filter((y) => y.startsWith("@container")).sort((y, S) => {
    var _, g;
    const T = /min-width:\s*([0-9.]+)/;
    return +(((_ = y.match(T)) == null ? void 0 : _[1]) || 0) - +(((g = S.match(T)) == null ? void 0 : g[1]) || 0);
  });
  return v.length ? v.reduce((y, S) => {
    const T = f[S];
    return delete y[S], y[S] = T, y;
  }, {
    ...f
  }) : f;
}
function iA(u, f) {
  return f === "@" || f.startsWith("@") && (u.some((v) => f.startsWith(`@${v}`)) || !!f.match(/^@\d/));
}
function oA(u, f) {
  const v = f.match(/^@([^/]+)?\/?(.+)?$/);
  if (!v) {
    if (DR.NODE_ENV !== "production")
      throw new Error(DR.NODE_ENV !== "production" ? `MUI: The provided shorthand ${`(${f})`} is invalid. The format should be \`@<breakpoint | number>\` or \`@<breakpoint | number>/<container>\`.
For example, \`@sm\` or \`@600\` or \`@40rem/sidebar\`.` : gs(18, `(${f})`));
    return null;
  }
  const [, y, S] = v, T = Number.isNaN(+y) ? y || 0 : +y;
  return u.containerQueries(S).up(T);
}
function lA(u) {
  const f = (T, _) => T.replace("@media", _ ? `@container ${_}` : "@container");
  function v(T, _) {
    T.up = (...g) => f(u.breakpoints.up(...g), _), T.down = (...g) => f(u.breakpoints.down(...g), _), T.between = (...g) => f(u.breakpoints.between(...g), _), T.only = (...g) => f(u.breakpoints.only(...g), _), T.not = (...g) => {
      const L = f(u.breakpoints.not(...g), _);
      return L.includes("not all and") ? L.replace("not all and ", "").replace("min-width:", "width<").replace("max-width:", "width>").replace("and", "or") : L;
    };
  }
  const y = {}, S = (T) => (v(y, T), y);
  return v(S), {
    ...u,
    containerQueries: S
  };
}
const fg = {
  xs: 0,
  // phone
  sm: 600,
  // tablet
  md: 900,
  // small laptop
  lg: 1200,
  // desktop
  xl: 1536
  // large screen
}, NR = {
  // Sorted ASC by size. That's important.
  // It can't be configured as it's used statically for propTypes.
  keys: ["xs", "sm", "md", "lg", "xl"],
  up: (u) => `@media (min-width:${fg[u]}px)`
}, uA = {
  containerQueries: (u) => ({
    up: (f) => {
      let v = typeof f == "number" ? f : fg[f] || f;
      return typeof v == "number" && (v = `${v}px`), u ? `@container ${u} (min-width:${v})` : `@container (min-width:${v})`;
    }
  })
};
function vu(u, f, v) {
  const y = u.theme || {};
  if (Array.isArray(f)) {
    const T = y.breakpoints || NR;
    return f.reduce((_, g, L) => (_[T.up(T.keys[L])] = v(f[L]), _), {});
  }
  if (typeof f == "object") {
    const T = y.breakpoints || NR;
    return Object.keys(f).reduce((_, g) => {
      if (iA(T.keys, g)) {
        const L = oA(y.containerQueries ? y : uA, g);
        L && (_[L] = v(f[g], g));
      } else if (Object.keys(T.values || fg).includes(g)) {
        const L = T.up(g);
        _[L] = v(f[g], g);
      } else {
        const L = g;
        _[L] = f[L];
      }
      return _;
    }, {});
  }
  return v(f);
}
function sA(u = {}) {
  var v;
  return ((v = u.keys) == null ? void 0 : v.reduce((y, S) => {
    const T = u.up(S);
    return y[T] = {}, y;
  }, {})) || {};
}
function cA(u, f) {
  return u.reduce((v, y) => {
    const S = v[y];
    return (!S || Object.keys(S).length === 0) && delete v[y], v;
  }, f);
}
var fA = {};
function dg(u, f, v = !0) {
  if (!f || typeof f != "string")
    return null;
  if (u && u.vars && v) {
    const y = `vars.${f}`.split(".").reduce((S, T) => S && S[T] ? S[T] : null, u);
    if (y != null)
      return y;
  }
  return f.split(".").reduce((y, S) => y && y[S] != null ? y[S] : null, u);
}
function ug(u, f, v, y = v) {
  let S;
  return typeof u == "function" ? S = u(v) : Array.isArray(u) ? S = u[v] || y : S = dg(u, v) || y, f && (S = f(S, y, u)), S;
}
function fr(u) {
  const {
    prop: f,
    cssProperty: v = u.prop,
    themeKey: y,
    transform: S
  } = u, T = (_) => {
    if (_[f] == null)
      return null;
    const g = _[f], L = _.theme, z = dg(L, y) || {};
    return vu(_, g, (F) => {
      let U = ug(z, S, F);
      return F === U && typeof F == "string" && (U = ug(z, S, `${f}${F === "default" ? "" : Fc(F)}`, F)), v === !1 ? U : {
        [v]: U
      };
    });
  };
  return T.propTypes = fA.NODE_ENV !== "production" ? {
    [f]: Es
  } : {}, T.filterProps = [f], T;
}
function dA(u) {
  const f = {};
  return (v) => (f[v] === void 0 && (f[v] = u(v)), f[v]);
}
var zd = {};
const pA = {
  m: "margin",
  p: "padding"
}, vA = {
  t: "Top",
  r: "Right",
  b: "Bottom",
  l: "Left",
  x: ["Left", "Right"],
  y: ["Top", "Bottom"]
}, AR = {
  marginX: "mx",
  marginY: "my",
  paddingX: "px",
  paddingY: "py"
}, hA = dA((u) => {
  if (u.length > 2)
    if (AR[u])
      u = AR[u];
    else
      return [u];
  const [f, v] = u.split(""), y = pA[f], S = vA[v] || "";
  return Array.isArray(S) ? S.map((T) => y + T) : [y + S];
}), pg = ["m", "mt", "mr", "mb", "ml", "mx", "my", "margin", "marginTop", "marginRight", "marginBottom", "marginLeft", "marginX", "marginY", "marginInline", "marginInlineStart", "marginInlineEnd", "marginBlock", "marginBlockStart", "marginBlockEnd"], vg = ["p", "pt", "pr", "pb", "pl", "px", "py", "padding", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "paddingX", "paddingY", "paddingInline", "paddingInlineStart", "paddingInlineEnd", "paddingBlock", "paddingBlockStart", "paddingBlockEnd"], mA = [...pg, ...vg];
function nh(u, f, v, y) {
  const S = dg(u, f, !0) ?? v;
  return typeof S == "number" || typeof S == "string" ? (T) => typeof T == "string" ? T : (zd.NODE_ENV !== "production" && typeof T != "number" && console.error(`MUI: Expected ${y} argument to be a number or a string, got ${T}.`), typeof S == "string" ? `calc(${T} * ${S})` : S * T) : Array.isArray(S) ? (T) => {
    if (typeof T == "string")
      return T;
    const _ = Math.abs(T);
    zd.NODE_ENV !== "production" && (Number.isInteger(_) ? _ > S.length - 1 && console.error([`MUI: The value provided (${_}) overflows.`, `The supported values are: ${JSON.stringify(S)}.`, `${_} > ${S.length - 1}, you need to add the missing values.`].join(`
`)) : console.error([`MUI: The \`theme.${f}\` array type cannot be combined with non integer values.You should either use an integer value that can be used as index, or define the \`theme.${f}\` as a number.`].join(`
`)));
    const g = S[_];
    return T >= 0 ? g : typeof g == "number" ? -g : `-${g}`;
  } : typeof S == "function" ? S : (zd.NODE_ENV !== "production" && console.error([`MUI: The \`theme.${f}\` value (${S}) is invalid.`, "It should be a number, an array or a function."].join(`
`)), () => {
  });
}
function mC(u) {
  return nh(u, "spacing", 8, "spacing");
}
function rh(u, f) {
  return typeof f == "string" || f == null ? f : u(f);
}
function yA(u, f) {
  return (v) => u.reduce((y, S) => (y[S] = rh(f, v), y), {});
}
function gA(u, f, v, y) {
  if (!f.includes(v))
    return null;
  const S = hA(v), T = yA(S, y), _ = u[v];
  return vu(u, _, T);
}
function fw(u, f) {
  const v = mC(u.theme);
  return Object.keys(u).map((y) => gA(u, f, y, v)).reduce(Kv, {});
}
function rr(u) {
  return fw(u, pg);
}
rr.propTypes = zd.NODE_ENV !== "production" ? pg.reduce((u, f) => (u[f] = Es, u), {}) : {};
rr.filterProps = pg;
function ar(u) {
  return fw(u, vg);
}
ar.propTypes = zd.NODE_ENV !== "production" ? vg.reduce((u, f) => (u[f] = Es, u), {}) : {};
ar.filterProps = vg;
zd.NODE_ENV !== "production" && mA.reduce((u, f) => (u[f] = Es, u), {});
var SA = {};
function hg(...u) {
  const f = u.reduce((y, S) => (S.filterProps.forEach((T) => {
    y[T] = S;
  }), y), {}), v = (y) => Object.keys(y).reduce((S, T) => f[T] ? Kv(S, f[T](y)) : S, {});
  return v.propTypes = SA.NODE_ENV !== "production" ? u.reduce((y, S) => Object.assign(y, S.propTypes), {}) : {}, v.filterProps = u.reduce((y, S) => y.concat(S.filterProps), []), v;
}
var EA = {};
function Ji(u) {
  return typeof u != "number" ? u : `${u}px solid`;
}
function Zi(u, f) {
  return fr({
    prop: u,
    themeKey: "borders",
    transform: f
  });
}
const CA = Zi("border", Ji), bA = Zi("borderTop", Ji), TA = Zi("borderRight", Ji), RA = Zi("borderBottom", Ji), wA = Zi("borderLeft", Ji), xA = Zi("borderColor"), _A = Zi("borderTopColor"), kA = Zi("borderRightColor"), OA = Zi("borderBottomColor"), DA = Zi("borderLeftColor"), NA = Zi("outline", Ji), AA = Zi("outlineColor"), mg = (u) => {
  if (u.borderRadius !== void 0 && u.borderRadius !== null) {
    const f = nh(u.theme, "shape.borderRadius", 4, "borderRadius"), v = (y) => ({
      borderRadius: rh(f, y)
    });
    return vu(u, u.borderRadius, v);
  }
  return null;
};
mg.propTypes = EA.NODE_ENV !== "production" ? {
  borderRadius: Es
} : {};
mg.filterProps = ["borderRadius"];
hg(CA, bA, TA, RA, wA, xA, _A, kA, OA, DA, mg, NA, AA);
var yC = {};
const yg = (u) => {
  if (u.gap !== void 0 && u.gap !== null) {
    const f = nh(u.theme, "spacing", 8, "gap"), v = (y) => ({
      gap: rh(f, y)
    });
    return vu(u, u.gap, v);
  }
  return null;
};
yg.propTypes = yC.NODE_ENV !== "production" ? {
  gap: Es
} : {};
yg.filterProps = ["gap"];
const gg = (u) => {
  if (u.columnGap !== void 0 && u.columnGap !== null) {
    const f = nh(u.theme, "spacing", 8, "columnGap"), v = (y) => ({
      columnGap: rh(f, y)
    });
    return vu(u, u.columnGap, v);
  }
  return null;
};
gg.propTypes = yC.NODE_ENV !== "production" ? {
  columnGap: Es
} : {};
gg.filterProps = ["columnGap"];
const Sg = (u) => {
  if (u.rowGap !== void 0 && u.rowGap !== null) {
    const f = nh(u.theme, "spacing", 8, "rowGap"), v = (y) => ({
      rowGap: rh(f, y)
    });
    return vu(u, u.rowGap, v);
  }
  return null;
};
Sg.propTypes = yC.NODE_ENV !== "production" ? {
  rowGap: Es
} : {};
Sg.filterProps = ["rowGap"];
const MA = fr({
  prop: "gridColumn"
}), LA = fr({
  prop: "gridRow"
}), zA = fr({
  prop: "gridAutoFlow"
}), UA = fr({
  prop: "gridAutoColumns"
}), PA = fr({
  prop: "gridAutoRows"
}), $A = fr({
  prop: "gridTemplateColumns"
}), FA = fr({
  prop: "gridTemplateRows"
}), jA = fr({
  prop: "gridTemplateAreas"
}), HA = fr({
  prop: "gridArea"
});
hg(yg, gg, Sg, MA, LA, zA, UA, PA, $A, FA, jA, HA);
function Ud(u, f) {
  return f === "grey" ? f : u;
}
const VA = fr({
  prop: "color",
  themeKey: "palette",
  transform: Ud
}), BA = fr({
  prop: "bgcolor",
  cssProperty: "backgroundColor",
  themeKey: "palette",
  transform: Ud
}), IA = fr({
  prop: "backgroundColor",
  themeKey: "palette",
  transform: Ud
});
hg(VA, BA, IA);
function _i(u) {
  return u <= 1 && u !== 0 ? `${u * 100}%` : u;
}
const YA = fr({
  prop: "width",
  transform: _i
}), gC = (u) => {
  if (u.maxWidth !== void 0 && u.maxWidth !== null) {
    const f = (v) => {
      var S, T, _, g, L;
      const y = ((_ = (T = (S = u.theme) == null ? void 0 : S.breakpoints) == null ? void 0 : T.values) == null ? void 0 : _[v]) || fg[v];
      return y ? ((L = (g = u.theme) == null ? void 0 : g.breakpoints) == null ? void 0 : L.unit) !== "px" ? {
        maxWidth: `${y}${u.theme.breakpoints.unit}`
      } : {
        maxWidth: y
      } : {
        maxWidth: _i(v)
      };
    };
    return vu(u, u.maxWidth, f);
  }
  return null;
};
gC.filterProps = ["maxWidth"];
const WA = fr({
  prop: "minWidth",
  transform: _i
}), GA = fr({
  prop: "height",
  transform: _i
}), QA = fr({
  prop: "maxHeight",
  transform: _i
}), qA = fr({
  prop: "minHeight",
  transform: _i
});
fr({
  prop: "size",
  cssProperty: "width",
  transform: _i
});
fr({
  prop: "size",
  cssProperty: "height",
  transform: _i
});
const KA = fr({
  prop: "boxSizing"
});
hg(YA, gC, WA, GA, QA, qA, KA);
const Eg = {
  // borders
  border: {
    themeKey: "borders",
    transform: Ji
  },
  borderTop: {
    themeKey: "borders",
    transform: Ji
  },
  borderRight: {
    themeKey: "borders",
    transform: Ji
  },
  borderBottom: {
    themeKey: "borders",
    transform: Ji
  },
  borderLeft: {
    themeKey: "borders",
    transform: Ji
  },
  borderColor: {
    themeKey: "palette"
  },
  borderTopColor: {
    themeKey: "palette"
  },
  borderRightColor: {
    themeKey: "palette"
  },
  borderBottomColor: {
    themeKey: "palette"
  },
  borderLeftColor: {
    themeKey: "palette"
  },
  outline: {
    themeKey: "borders",
    transform: Ji
  },
  outlineColor: {
    themeKey: "palette"
  },
  borderRadius: {
    themeKey: "shape.borderRadius",
    style: mg
  },
  // palette
  color: {
    themeKey: "palette",
    transform: Ud
  },
  bgcolor: {
    themeKey: "palette",
    cssProperty: "backgroundColor",
    transform: Ud
  },
  backgroundColor: {
    themeKey: "palette",
    transform: Ud
  },
  // spacing
  p: {
    style: ar
  },
  pt: {
    style: ar
  },
  pr: {
    style: ar
  },
  pb: {
    style: ar
  },
  pl: {
    style: ar
  },
  px: {
    style: ar
  },
  py: {
    style: ar
  },
  padding: {
    style: ar
  },
  paddingTop: {
    style: ar
  },
  paddingRight: {
    style: ar
  },
  paddingBottom: {
    style: ar
  },
  paddingLeft: {
    style: ar
  },
  paddingX: {
    style: ar
  },
  paddingY: {
    style: ar
  },
  paddingInline: {
    style: ar
  },
  paddingInlineStart: {
    style: ar
  },
  paddingInlineEnd: {
    style: ar
  },
  paddingBlock: {
    style: ar
  },
  paddingBlockStart: {
    style: ar
  },
  paddingBlockEnd: {
    style: ar
  },
  m: {
    style: rr
  },
  mt: {
    style: rr
  },
  mr: {
    style: rr
  },
  mb: {
    style: rr
  },
  ml: {
    style: rr
  },
  mx: {
    style: rr
  },
  my: {
    style: rr
  },
  margin: {
    style: rr
  },
  marginTop: {
    style: rr
  },
  marginRight: {
    style: rr
  },
  marginBottom: {
    style: rr
  },
  marginLeft: {
    style: rr
  },
  marginX: {
    style: rr
  },
  marginY: {
    style: rr
  },
  marginInline: {
    style: rr
  },
  marginInlineStart: {
    style: rr
  },
  marginInlineEnd: {
    style: rr
  },
  marginBlock: {
    style: rr
  },
  marginBlockStart: {
    style: rr
  },
  marginBlockEnd: {
    style: rr
  },
  // display
  displayPrint: {
    cssProperty: !1,
    transform: (u) => ({
      "@media print": {
        display: u
      }
    })
  },
  display: {},
  overflow: {},
  textOverflow: {},
  visibility: {},
  whiteSpace: {},
  // flexbox
  flexBasis: {},
  flexDirection: {},
  flexWrap: {},
  justifyContent: {},
  alignItems: {},
  alignContent: {},
  order: {},
  flex: {},
  flexGrow: {},
  flexShrink: {},
  alignSelf: {},
  justifyItems: {},
  justifySelf: {},
  // grid
  gap: {
    style: yg
  },
  rowGap: {
    style: Sg
  },
  columnGap: {
    style: gg
  },
  gridColumn: {},
  gridRow: {},
  gridAutoFlow: {},
  gridAutoColumns: {},
  gridAutoRows: {},
  gridTemplateColumns: {},
  gridTemplateRows: {},
  gridTemplateAreas: {},
  gridArea: {},
  // positions
  position: {},
  zIndex: {
    themeKey: "zIndex"
  },
  top: {},
  right: {},
  bottom: {},
  left: {},
  // shadows
  boxShadow: {
    themeKey: "shadows"
  },
  // sizing
  width: {
    transform: _i
  },
  maxWidth: {
    style: gC
  },
  minWidth: {
    transform: _i
  },
  height: {
    transform: _i
  },
  maxHeight: {
    transform: _i
  },
  minHeight: {
    transform: _i
  },
  boxSizing: {},
  // typography
  font: {
    themeKey: "font"
  },
  fontFamily: {
    themeKey: "typography"
  },
  fontSize: {
    themeKey: "typography"
  },
  fontStyle: {
    themeKey: "typography"
  },
  fontWeight: {
    themeKey: "typography"
  },
  letterSpacing: {},
  textTransform: {},
  lineHeight: {},
  textAlign: {},
  typography: {
    cssProperty: !1,
    themeKey: "typography"
  }
};
function XA(...u) {
  const f = u.reduce((y, S) => y.concat(Object.keys(S)), []), v = new Set(f);
  return u.every((y) => v.size === Object.keys(y).length);
}
function JA(u, f) {
  return typeof u == "function" ? u(f) : u;
}
function ZA() {
  function u(v, y, S, T) {
    const _ = {
      [v]: y,
      theme: S
    }, g = T[v];
    if (!g)
      return {
        [v]: y
      };
    const {
      cssProperty: L = v,
      themeKey: z,
      transform: A,
      style: F
    } = g;
    if (y == null)
      return null;
    if (z === "typography" && y === "inherit")
      return {
        [v]: y
      };
    const U = dg(S, z) || {};
    return F ? F(_) : vu(_, y, (B) => {
      let M = ug(U, A, B);
      return B === M && typeof B == "string" && (M = ug(U, A, `${v}${B === "default" ? "" : Fc(B)}`, B)), L === !1 ? M : {
        [L]: M
      };
    });
  }
  function f(v) {
    const {
      sx: y,
      theme: S = {}
    } = v || {};
    if (!y)
      return null;
    const T = S.unstable_sxConfig ?? Eg;
    function _(g) {
      let L = g;
      if (typeof g == "function")
        L = g(S);
      else if (typeof g != "object")
        return g;
      if (!L)
        return null;
      const z = sA(S.breakpoints), A = Object.keys(z);
      let F = z;
      return Object.keys(L).forEach((U) => {
        const te = JA(L[U], S);
        if (te != null)
          if (typeof te == "object")
            if (T[U])
              F = Kv(F, u(U, te, S, T));
            else {
              const B = vu({
                theme: S
              }, te, (M) => ({
                [U]: M
              }));
              XA(B, te) ? F[U] = f({
                sx: te,
                theme: S
              }) : F = Kv(F, B);
            }
          else
            F = Kv(F, u(U, te, S, T));
      }), aA(S, cA(A, F));
    }
    return Array.isArray(y) ? y.map(_) : _(y);
  }
  return f;
}
const $d = ZA();
$d.filterProps = ["sx"];
function lC() {
  return lC = Object.assign ? Object.assign.bind() : function(u) {
    for (var f = 1; f < arguments.length; f++) {
      var v = arguments[f];
      for (var y in v) ({}).hasOwnProperty.call(v, y) && (u[y] = v[y]);
    }
    return u;
  }, lC.apply(null, arguments);
}
function eM(u) {
  if (u.sheet)
    return u.sheet;
  for (var f = 0; f < document.styleSheets.length; f++)
    if (document.styleSheets[f].ownerNode === u)
      return document.styleSheets[f];
}
function tM(u) {
  var f = document.createElement("style");
  return f.setAttribute("data-emotion", u.key), u.nonce !== void 0 && f.setAttribute("nonce", u.nonce), f.appendChild(document.createTextNode("")), f.setAttribute("data-s", ""), f;
}
var nM = /* @__PURE__ */ function() {
  function u(v) {
    var y = this;
    this._insertTag = function(S) {
      var T;
      y.tags.length === 0 ? y.insertionPoint ? T = y.insertionPoint.nextSibling : y.prepend ? T = y.container.firstChild : T = y.before : T = y.tags[y.tags.length - 1].nextSibling, y.container.insertBefore(S, T), y.tags.push(S);
    }, this.isSpeedy = v.speedy === void 0 ? !0 : v.speedy, this.tags = [], this.ctr = 0, this.nonce = v.nonce, this.key = v.key, this.container = v.container, this.prepend = v.prepend, this.insertionPoint = v.insertionPoint, this.before = null;
  }
  var f = u.prototype;
  return f.hydrate = function(y) {
    y.forEach(this._insertTag);
  }, f.insert = function(y) {
    this.ctr % (this.isSpeedy ? 65e3 : 1) === 0 && this._insertTag(tM(this));
    var S = this.tags[this.tags.length - 1];
    if (this.isSpeedy) {
      var T = eM(S);
      try {
        T.insertRule(y, T.cssRules.length);
      } catch {
      }
    } else
      S.appendChild(document.createTextNode(y));
    this.ctr++;
  }, f.flush = function() {
    this.tags.forEach(function(y) {
      var S;
      return (S = y.parentNode) == null ? void 0 : S.removeChild(y);
    }), this.tags = [], this.ctr = 0;
  }, u;
}(), xa = "-ms-", sg = "-moz-", nn = "-webkit-", dw = "comm", SC = "rule", EC = "decl", rM = "@import", pw = "@keyframes", aM = "@layer", iM = Math.abs, Cg = String.fromCharCode, oM = Object.assign;
function lM(u, f) {
  return oa(u, 0) ^ 45 ? (((f << 2 ^ oa(u, 0)) << 2 ^ oa(u, 1)) << 2 ^ oa(u, 2)) << 2 ^ oa(u, 3) : 0;
}
function vw(u) {
  return u.trim();
}
function uM(u, f) {
  return (u = f.exec(u)) ? u[0] : u;
}
function rn(u, f, v) {
  return u.replace(f, v);
}
function uC(u, f) {
  return u.indexOf(f);
}
function oa(u, f) {
  return u.charCodeAt(f) | 0;
}
function Xv(u, f, v) {
  return u.slice(f, v);
}
function ml(u) {
  return u.length;
}
function CC(u) {
  return u.length;
}
function Zy(u, f) {
  return f.push(u), u;
}
function sM(u, f) {
  return u.map(f).join("");
}
var bg = 1, Fd = 1, hw = 0, fi = 0, Cr = 0, Hd = "";
function Tg(u, f, v, y, S, T, _) {
  return { value: u, root: f, parent: v, type: y, props: S, children: T, line: bg, column: Fd, length: _, return: "" };
}
function Bv(u, f) {
  return oM(Tg("", null, null, "", null, null, 0), u, { length: -u.length }, f);
}
function cM() {
  return Cr;
}
function fM() {
  return Cr = fi > 0 ? oa(Hd, --fi) : 0, Fd--, Cr === 10 && (Fd = 1, bg--), Cr;
}
function Oi() {
  return Cr = fi < hw ? oa(Hd, fi++) : 0, Fd++, Cr === 10 && (Fd = 1, bg++), Cr;
}
function gl() {
  return oa(Hd, fi);
}
function rg() {
  return fi;
}
function ah(u, f) {
  return Xv(Hd, u, f);
}
function Jv(u) {
  switch (u) {
    case 0:
    case 9:
    case 10:
    case 13:
    case 32:
      return 5;
    case 33:
    case 43:
    case 44:
    case 47:
    case 62:
    case 64:
    case 126:
    case 59:
    case 123:
    case 125:
      return 4;
    case 58:
      return 3;
    case 34:
    case 39:
    case 40:
    case 91:
      return 2;
    case 41:
    case 93:
      return 1;
  }
  return 0;
}
function mw(u) {
  return bg = Fd = 1, hw = ml(Hd = u), fi = 0, [];
}
function yw(u) {
  return Hd = "", u;
}
function ag(u) {
  return vw(ah(fi - 1, sC(u === 91 ? u + 2 : u === 40 ? u + 1 : u)));
}
function dM(u) {
  for (; (Cr = gl()) && Cr < 33; )
    Oi();
  return Jv(u) > 2 || Jv(Cr) > 3 ? "" : " ";
}
function pM(u, f) {
  for (; --f && Oi() && !(Cr < 48 || Cr > 102 || Cr > 57 && Cr < 65 || Cr > 70 && Cr < 97); )
    ;
  return ah(u, rg() + (f < 6 && gl() == 32 && Oi() == 32));
}
function sC(u) {
  for (; Oi(); )
    switch (Cr) {
      case u:
        return fi;
      case 34:
      case 39:
        u !== 34 && u !== 39 && sC(Cr);
        break;
      case 40:
        u === 41 && sC(u);
        break;
      case 92:
        Oi();
        break;
    }
  return fi;
}
function vM(u, f) {
  for (; Oi() && u + Cr !== 57; )
    if (u + Cr === 84 && gl() === 47)
      break;
  return "/*" + ah(f, fi - 1) + "*" + Cg(u === 47 ? u : Oi());
}
function hM(u) {
  for (; !Jv(gl()); )
    Oi();
  return ah(u, fi);
}
function mM(u) {
  return yw(ig("", null, null, null, [""], u = mw(u), 0, [0], u));
}
function ig(u, f, v, y, S, T, _, g, L) {
  for (var z = 0, A = 0, F = _, U = 0, te = 0, B = 0, M = 1, j = 1, ce = 1, De = 0, de = "", ue = S, q = T, se = y, Ce = de; j; )
    switch (B = De, De = Oi()) {
      case 40:
        if (B != 108 && oa(Ce, F - 1) == 58) {
          uC(Ce += rn(ag(De), "&", "&\f"), "&\f") != -1 && (ce = -1);
          break;
        }
      case 34:
      case 39:
      case 91:
        Ce += ag(De);
        break;
      case 9:
      case 10:
      case 13:
      case 32:
        Ce += dM(B);
        break;
      case 92:
        Ce += pM(rg() - 1, 7);
        continue;
      case 47:
        switch (gl()) {
          case 42:
          case 47:
            Zy(yM(vM(Oi(), rg()), f, v), L);
            break;
          default:
            Ce += "/";
        }
        break;
      case 123 * M:
        g[z++] = ml(Ce) * ce;
      case 125 * M:
      case 59:
      case 0:
        switch (De) {
          case 0:
          case 125:
            j = 0;
          case 59 + A:
            ce == -1 && (Ce = rn(Ce, /\f/g, "")), te > 0 && ml(Ce) - F && Zy(te > 32 ? LR(Ce + ";", y, v, F - 1) : LR(rn(Ce, " ", "") + ";", y, v, F - 2), L);
            break;
          case 59:
            Ce += ";";
          default:
            if (Zy(se = MR(Ce, f, v, z, A, S, g, de, ue = [], q = [], F), T), De === 123)
              if (A === 0)
                ig(Ce, f, se, se, ue, T, F, g, q);
              else
                switch (U === 99 && oa(Ce, 3) === 110 ? 100 : U) {
                  case 100:
                  case 108:
                  case 109:
                  case 115:
                    ig(u, se, se, y && Zy(MR(u, se, se, 0, 0, S, g, de, S, ue = [], F), q), S, q, F, g, y ? ue : q);
                    break;
                  default:
                    ig(Ce, se, se, se, [""], q, 0, g, q);
                }
        }
        z = A = te = 0, M = ce = 1, de = Ce = "", F = _;
        break;
      case 58:
        F = 1 + ml(Ce), te = B;
      default:
        if (M < 1) {
          if (De == 123)
            --M;
          else if (De == 125 && M++ == 0 && fM() == 125)
            continue;
        }
        switch (Ce += Cg(De), De * M) {
          case 38:
            ce = A > 0 ? 1 : (Ce += "\f", -1);
            break;
          case 44:
            g[z++] = (ml(Ce) - 1) * ce, ce = 1;
            break;
          case 64:
            gl() === 45 && (Ce += ag(Oi())), U = gl(), A = F = ml(de = Ce += hM(rg())), De++;
            break;
          case 45:
            B === 45 && ml(Ce) == 2 && (M = 0);
        }
    }
  return T;
}
function MR(u, f, v, y, S, T, _, g, L, z, A) {
  for (var F = S - 1, U = S === 0 ? T : [""], te = CC(U), B = 0, M = 0, j = 0; B < y; ++B)
    for (var ce = 0, De = Xv(u, F + 1, F = iM(M = _[B])), de = u; ce < te; ++ce)
      (de = vw(M > 0 ? U[ce] + " " + De : rn(De, /&\f/g, U[ce]))) && (L[j++] = de);
  return Tg(u, f, v, S === 0 ? SC : g, L, z, A);
}
function yM(u, f, v) {
  return Tg(u, f, v, dw, Cg(cM()), Xv(u, 2, -2), 0);
}
function LR(u, f, v, y) {
  return Tg(u, f, v, EC, Xv(u, 0, y), Xv(u, y + 1, -1), y);
}
function Pd(u, f) {
  for (var v = "", y = CC(u), S = 0; S < y; S++)
    v += f(u[S], S, u, f) || "";
  return v;
}
function gM(u, f, v, y) {
  switch (u.type) {
    case aM:
      if (u.children.length) break;
    case rM:
    case EC:
      return u.return = u.return || u.value;
    case dw:
      return "";
    case pw:
      return u.return = u.value + "{" + Pd(u.children, y) + "}";
    case SC:
      u.value = u.props.join(",");
  }
  return ml(v = Pd(u.children, y)) ? u.return = u.value + "{" + v + "}" : "";
}
function SM(u) {
  var f = CC(u);
  return function(v, y, S, T) {
    for (var _ = "", g = 0; g < f; g++)
      _ += u[g](v, y, S, T) || "";
    return _;
  };
}
function EM(u) {
  return function(f) {
    f.root || (f = f.return) && u(f);
  };
}
function gw(u) {
  var f = /* @__PURE__ */ Object.create(null);
  return function(v) {
    return f[v] === void 0 && (f[v] = u(v)), f[v];
  };
}
var CM = function(f, v, y) {
  for (var S = 0, T = 0; S = T, T = gl(), S === 38 && T === 12 && (v[y] = 1), !Jv(T); )
    Oi();
  return ah(f, fi);
}, bM = function(f, v) {
  var y = -1, S = 44;
  do
    switch (Jv(S)) {
      case 0:
        S === 38 && gl() === 12 && (v[y] = 1), f[y] += CM(fi - 1, v, y);
        break;
      case 2:
        f[y] += ag(S);
        break;
      case 4:
        if (S === 44) {
          f[++y] = gl() === 58 ? "&\f" : "", v[y] = f[y].length;
          break;
        }
      default:
        f[y] += Cg(S);
    }
  while (S = Oi());
  return f;
}, TM = function(f, v) {
  return yw(bM(mw(f), v));
}, zR = /* @__PURE__ */ new WeakMap(), RM = function(f) {
  if (!(f.type !== "rule" || !f.parent || // positive .length indicates that this rule contains pseudo
  // negative .length indicates that this rule has been already prefixed
  f.length < 1)) {
    for (var v = f.value, y = f.parent, S = f.column === y.column && f.line === y.line; y.type !== "rule"; )
      if (y = y.parent, !y) return;
    if (!(f.props.length === 1 && v.charCodeAt(0) !== 58 && !zR.get(y)) && !S) {
      zR.set(f, !0);
      for (var T = [], _ = TM(v, T), g = y.props, L = 0, z = 0; L < _.length; L++)
        for (var A = 0; A < g.length; A++, z++)
          f.props[z] = T[L] ? _[L].replace(/&\f/g, g[A]) : g[A] + " " + _[L];
    }
  }
}, wM = function(f) {
  if (f.type === "decl") {
    var v = f.value;
    // charcode for l
    v.charCodeAt(0) === 108 && // charcode for b
    v.charCodeAt(2) === 98 && (f.return = "", f.value = "");
  }
};
function Sw(u, f) {
  switch (lM(u, f)) {
    case 5103:
      return nn + "print-" + u + u;
    case 5737:
    case 4201:
    case 3177:
    case 3433:
    case 1641:
    case 4457:
    case 2921:
    case 5572:
    case 6356:
    case 5844:
    case 3191:
    case 6645:
    case 3005:
    case 6391:
    case 5879:
    case 5623:
    case 6135:
    case 4599:
    case 4855:
    case 4215:
    case 6389:
    case 5109:
    case 5365:
    case 5621:
    case 3829:
      return nn + u + u;
    case 5349:
    case 4246:
    case 4810:
    case 6968:
    case 2756:
      return nn + u + sg + u + xa + u + u;
    case 6828:
    case 4268:
      return nn + u + xa + u + u;
    case 6165:
      return nn + u + xa + "flex-" + u + u;
    case 5187:
      return nn + u + rn(u, /(\w+).+(:[^]+)/, nn + "box-$1$2" + xa + "flex-$1$2") + u;
    case 5443:
      return nn + u + xa + "flex-item-" + rn(u, /flex-|-self/, "") + u;
    case 4675:
      return nn + u + xa + "flex-line-pack" + rn(u, /align-content|flex-|-self/, "") + u;
    case 5548:
      return nn + u + xa + rn(u, "shrink", "negative") + u;
    case 5292:
      return nn + u + xa + rn(u, "basis", "preferred-size") + u;
    case 6060:
      return nn + "box-" + rn(u, "-grow", "") + nn + u + xa + rn(u, "grow", "positive") + u;
    case 4554:
      return nn + rn(u, /([^-])(transform)/g, "$1" + nn + "$2") + u;
    case 6187:
      return rn(rn(rn(u, /(zoom-|grab)/, nn + "$1"), /(image-set)/, nn + "$1"), u, "") + u;
    case 5495:
    case 3959:
      return rn(u, /(image-set\([^]*)/, nn + "$1$`$1");
    case 4968:
      return rn(rn(u, /(.+:)(flex-)?(.*)/, nn + "box-pack:$3" + xa + "flex-pack:$3"), /s.+-b[^;]+/, "justify") + nn + u + u;
    case 4095:
    case 3583:
    case 4068:
    case 2532:
      return rn(u, /(.+)-inline(.+)/, nn + "$1$2") + u;
    case 8116:
    case 7059:
    case 5753:
    case 5535:
    case 5445:
    case 5701:
    case 4933:
    case 4677:
    case 5533:
    case 5789:
    case 5021:
    case 4765:
      if (ml(u) - 1 - f > 6) switch (oa(u, f + 1)) {
        case 109:
          if (oa(u, f + 4) !== 45) break;
        case 102:
          return rn(u, /(.+:)(.+)-([^]+)/, "$1" + nn + "$2-$3$1" + sg + (oa(u, f + 3) == 108 ? "$3" : "$2-$3")) + u;
        case 115:
          return ~uC(u, "stretch") ? Sw(rn(u, "stretch", "fill-available"), f) + u : u;
      }
      break;
    case 4949:
      if (oa(u, f + 1) !== 115) break;
    case 6444:
      switch (oa(u, ml(u) - 3 - (~uC(u, "!important") && 10))) {
        case 107:
          return rn(u, ":", ":" + nn) + u;
        case 101:
          return rn(u, /(.+:)([^;!]+)(;|!.+)?/, "$1" + nn + (oa(u, 14) === 45 ? "inline-" : "") + "box$3$1" + nn + "$2$3$1" + xa + "$2box$3") + u;
      }
      break;
    case 5936:
      switch (oa(u, f + 11)) {
        case 114:
          return nn + u + xa + rn(u, /[svh]\w+-[tblr]{2}/, "tb") + u;
        case 108:
          return nn + u + xa + rn(u, /[svh]\w+-[tblr]{2}/, "tb-rl") + u;
        case 45:
          return nn + u + xa + rn(u, /[svh]\w+-[tblr]{2}/, "lr") + u;
      }
      return nn + u + xa + u + u;
  }
  return u;
}
var xM = function(f, v, y, S) {
  if (f.length > -1 && !f.return) switch (f.type) {
    case EC:
      f.return = Sw(f.value, f.length);
      break;
    case pw:
      return Pd([Bv(f, {
        value: rn(f.value, "@", "@" + nn)
      })], S);
    case SC:
      if (f.length) return sM(f.props, function(T) {
        switch (uM(T, /(::plac\w+|:read-\w+)/)) {
          case ":read-only":
          case ":read-write":
            return Pd([Bv(f, {
              props: [rn(T, /:(read-\w+)/, ":" + sg + "$1")]
            })], S);
          case "::placeholder":
            return Pd([Bv(f, {
              props: [rn(T, /:(plac\w+)/, ":" + nn + "input-$1")]
            }), Bv(f, {
              props: [rn(T, /:(plac\w+)/, ":" + sg + "$1")]
            }), Bv(f, {
              props: [rn(T, /:(plac\w+)/, xa + "input-$1")]
            })], S);
        }
        return "";
      });
  }
}, _M = [xM], kM = function(f) {
  var v = f.key;
  if (v === "css") {
    var y = document.querySelectorAll("style[data-emotion]:not([data-s])");
    Array.prototype.forEach.call(y, function(M) {
      var j = M.getAttribute("data-emotion");
      j.indexOf(" ") !== -1 && (document.head.appendChild(M), M.setAttribute("data-s", ""));
    });
  }
  var S = f.stylisPlugins || _M, T = {}, _, g = [];
  _ = f.container || document.head, Array.prototype.forEach.call(
    // this means we will ignore elements which don't have a space in them which
    // means that the style elements we're looking at are only Emotion 11 server-rendered style elements
    document.querySelectorAll('style[data-emotion^="' + v + ' "]'),
    function(M) {
      for (var j = M.getAttribute("data-emotion").split(" "), ce = 1; ce < j.length; ce++)
        T[j[ce]] = !0;
      g.push(M);
    }
  );
  var L, z = [RM, wM];
  {
    var A, F = [gM, EM(function(M) {
      A.insert(M);
    })], U = SM(z.concat(S, F)), te = function(j) {
      return Pd(mM(j), U);
    };
    L = function(j, ce, De, de) {
      A = De, te(j ? j + "{" + ce.styles + "}" : ce.styles), de && (B.inserted[ce.name] = !0);
    };
  }
  var B = {
    key: v,
    sheet: new nM({
      key: v,
      container: _,
      nonce: f.nonce,
      speedy: f.speedy,
      prepend: f.prepend,
      insertionPoint: f.insertionPoint
    }),
    nonce: f.nonce,
    inserted: T,
    registered: {},
    insert: L
  };
  return B.sheet.hydrate(g), B;
}, OM = !0;
function DM(u, f, v) {
  var y = "";
  return v.split(" ").forEach(function(S) {
    u[S] !== void 0 ? f.push(u[S] + ";") : S && (y += S + " ");
  }), y;
}
var Ew = function(f, v, y) {
  var S = f.key + "-" + v.name;
  // we only need to add the styles to the registered cache if the
  // class name could be used further down
  // the tree but if it's a string tag, we know it won't
  // so we don't have to add it to registered cache.
  // this improves memory usage since we can avoid storing the whole style string
  (y === !1 || // we need to always store it if we're in compat mode and
  // in node since emotion-server relies on whether a style is in
  // the registered cache to know whether a style is global or not
  // also, note that this check will be dead code eliminated in the browser
  OM === !1) && f.registered[S] === void 0 && (f.registered[S] = v.styles);
}, NM = function(f, v, y) {
  Ew(f, v, y);
  var S = f.key + "-" + v.name;
  if (f.inserted[v.name] === void 0) {
    var T = v;
    do
      f.insert(v === T ? "." + S : "", T, f.sheet, !0), T = T.next;
    while (T !== void 0);
  }
};
function AM(u) {
  for (var f = 0, v, y = 0, S = u.length; S >= 4; ++y, S -= 4)
    v = u.charCodeAt(y) & 255 | (u.charCodeAt(++y) & 255) << 8 | (u.charCodeAt(++y) & 255) << 16 | (u.charCodeAt(++y) & 255) << 24, v = /* Math.imul(k, m): */
    (v & 65535) * 1540483477 + ((v >>> 16) * 59797 << 16), v ^= /* k >>> r: */
    v >>> 24, f = /* Math.imul(k, m): */
    (v & 65535) * 1540483477 + ((v >>> 16) * 59797 << 16) ^ /* Math.imul(h, m): */
    (f & 65535) * 1540483477 + ((f >>> 16) * 59797 << 16);
  switch (S) {
    case 3:
      f ^= (u.charCodeAt(y + 2) & 255) << 16;
    case 2:
      f ^= (u.charCodeAt(y + 1) & 255) << 8;
    case 1:
      f ^= u.charCodeAt(y) & 255, f = /* Math.imul(h, m): */
      (f & 65535) * 1540483477 + ((f >>> 16) * 59797 << 16);
  }
  return f ^= f >>> 13, f = /* Math.imul(h, m): */
  (f & 65535) * 1540483477 + ((f >>> 16) * 59797 << 16), ((f ^ f >>> 15) >>> 0).toString(36);
}
var MM = {
  animationIterationCount: 1,
  aspectRatio: 1,
  borderImageOutset: 1,
  borderImageSlice: 1,
  borderImageWidth: 1,
  boxFlex: 1,
  boxFlexGroup: 1,
  boxOrdinalGroup: 1,
  columnCount: 1,
  columns: 1,
  flex: 1,
  flexGrow: 1,
  flexPositive: 1,
  flexShrink: 1,
  flexNegative: 1,
  flexOrder: 1,
  gridRow: 1,
  gridRowEnd: 1,
  gridRowSpan: 1,
  gridRowStart: 1,
  gridColumn: 1,
  gridColumnEnd: 1,
  gridColumnSpan: 1,
  gridColumnStart: 1,
  msGridRow: 1,
  msGridRowSpan: 1,
  msGridColumn: 1,
  msGridColumnSpan: 1,
  fontWeight: 1,
  lineHeight: 1,
  opacity: 1,
  order: 1,
  orphans: 1,
  scale: 1,
  tabSize: 1,
  widows: 1,
  zIndex: 1,
  zoom: 1,
  WebkitLineClamp: 1,
  // SVG-related properties
  fillOpacity: 1,
  floodOpacity: 1,
  stopOpacity: 1,
  strokeDasharray: 1,
  strokeDashoffset: 1,
  strokeMiterlimit: 1,
  strokeOpacity: 1,
  strokeWidth: 1
}, LM = /[A-Z]|^ms/g, zM = /_EMO_([^_]+?)_([^]*?)_EMO_/g, Cw = function(f) {
  return f.charCodeAt(1) === 45;
}, UR = function(f) {
  return f != null && typeof f != "boolean";
}, KE = /* @__PURE__ */ gw(function(u) {
  return Cw(u) ? u : u.replace(LM, "-$&").toLowerCase();
}), PR = function(f, v) {
  switch (f) {
    case "animation":
    case "animationName":
      if (typeof v == "string")
        return v.replace(zM, function(y, S, T) {
          return yl = {
            name: S,
            styles: T,
            next: yl
          }, S;
        });
  }
  return MM[f] !== 1 && !Cw(f) && typeof v == "number" && v !== 0 ? v + "px" : v;
};
function Zv(u, f, v) {
  if (v == null)
    return "";
  var y = v;
  if (y.__emotion_styles !== void 0)
    return y;
  switch (typeof v) {
    case "boolean":
      return "";
    case "object": {
      var S = v;
      if (S.anim === 1)
        return yl = {
          name: S.name,
          styles: S.styles,
          next: yl
        }, S.name;
      var T = v;
      if (T.styles !== void 0) {
        var _ = T.next;
        if (_ !== void 0)
          for (; _ !== void 0; )
            yl = {
              name: _.name,
              styles: _.styles,
              next: yl
            }, _ = _.next;
        var g = T.styles + ";";
        return g;
      }
      return UM(u, f, v);
    }
    case "function": {
      if (u !== void 0) {
        var L = yl, z = v(u);
        return yl = L, Zv(u, f, z);
      }
      break;
    }
  }
  var A = v;
  if (f == null)
    return A;
  var F = f[A];
  return F !== void 0 ? F : A;
}
function UM(u, f, v) {
  var y = "";
  if (Array.isArray(v))
    for (var S = 0; S < v.length; S++)
      y += Zv(u, f, v[S]) + ";";
  else
    for (var T in v) {
      var _ = v[T];
      if (typeof _ != "object") {
        var g = _;
        f != null && f[g] !== void 0 ? y += T + "{" + f[g] + "}" : UR(g) && (y += KE(T) + ":" + PR(T, g) + ";");
      } else if (Array.isArray(_) && typeof _[0] == "string" && (f == null || f[_[0]] === void 0))
        for (var L = 0; L < _.length; L++)
          UR(_[L]) && (y += KE(T) + ":" + PR(T, _[L]) + ";");
      else {
        var z = Zv(u, f, _);
        switch (T) {
          case "animation":
          case "animationName": {
            y += KE(T) + ":" + z + ";";
            break;
          }
          default:
            y += T + "{" + z + "}";
        }
      }
    }
  return y;
}
var $R = /label:\s*([^\s;{]+)\s*(;|$)/g, yl;
function bw(u, f, v) {
  if (u.length === 1 && typeof u[0] == "object" && u[0] !== null && u[0].styles !== void 0)
    return u[0];
  var y = !0, S = "";
  yl = void 0;
  var T = u[0];
  if (T == null || T.raw === void 0)
    y = !1, S += Zv(v, f, T);
  else {
    var _ = T;
    S += _[0];
  }
  for (var g = 1; g < u.length; g++)
    if (S += Zv(v, f, u[g]), y) {
      var L = T;
      S += L[g];
    }
  $R.lastIndex = 0;
  for (var z = "", A; (A = $R.exec(S)) !== null; )
    z += "-" + A[1];
  var F = AM(S) + z;
  return {
    name: F,
    styles: S,
    next: yl
  };
}
var PM = function(f) {
  return f();
}, $M = cR.useInsertionEffect ? cR.useInsertionEffect : !1, FM = $M || PM, Tw = /* @__PURE__ */ Vt.createContext(
  // we're doing this to avoid preconstruct's dead code elimination in this one case
  // because this module is primarily intended for the browser and node
  // but it's also required in react native and similar environments sometimes
  // and we could have a special build just for that
  // but this is much easier and the native packages
  // might use a different theme context in the future anyway
  typeof HTMLElement < "u" ? /* @__PURE__ */ kM({
    key: "css"
  }) : null
);
Tw.Provider;
var jM = function(f) {
  return /* @__PURE__ */ Vt.forwardRef(function(v, y) {
    var S = Vt.useContext(Tw);
    return f(v, S, y);
  });
}, HM = /* @__PURE__ */ Vt.createContext({}), VM = /^((children|dangerouslySetInnerHTML|key|ref|autoFocus|defaultValue|defaultChecked|innerHTML|suppressContentEditableWarning|suppressHydrationWarning|valueLink|abbr|accept|acceptCharset|accessKey|action|allow|allowUserMedia|allowPaymentRequest|allowFullScreen|allowTransparency|alt|async|autoComplete|autoPlay|capture|cellPadding|cellSpacing|challenge|charSet|checked|cite|classID|className|cols|colSpan|content|contentEditable|contextMenu|controls|controlsList|coords|crossOrigin|data|dateTime|decoding|default|defer|dir|disabled|disablePictureInPicture|disableRemotePlayback|download|draggable|encType|enterKeyHint|fetchpriority|fetchPriority|form|formAction|formEncType|formMethod|formNoValidate|formTarget|frameBorder|headers|height|hidden|high|href|hrefLang|htmlFor|httpEquiv|id|inputMode|integrity|is|keyParams|keyType|kind|label|lang|list|loading|loop|low|marginHeight|marginWidth|max|maxLength|media|mediaGroup|method|min|minLength|multiple|muted|name|nonce|noValidate|open|optimum|pattern|placeholder|playsInline|poster|preload|profile|radioGroup|readOnly|referrerPolicy|rel|required|reversed|role|rows|rowSpan|sandbox|scope|scoped|scrolling|seamless|selected|shape|size|sizes|slot|span|spellCheck|src|srcDoc|srcLang|srcSet|start|step|style|summary|tabIndex|target|title|translate|type|useMap|value|width|wmode|wrap|about|datatype|inlist|prefix|property|resource|typeof|vocab|autoCapitalize|autoCorrect|autoSave|color|incremental|fallback|inert|itemProp|itemScope|itemType|itemID|itemRef|on|option|results|security|unselectable|accentHeight|accumulate|additive|alignmentBaseline|allowReorder|alphabetic|amplitude|arabicForm|ascent|attributeName|attributeType|autoReverse|azimuth|baseFrequency|baselineShift|baseProfile|bbox|begin|bias|by|calcMode|capHeight|clip|clipPathUnits|clipPath|clipRule|colorInterpolation|colorInterpolationFilters|colorProfile|colorRendering|contentScriptType|contentStyleType|cursor|cx|cy|d|decelerate|descent|diffuseConstant|direction|display|divisor|dominantBaseline|dur|dx|dy|edgeMode|elevation|enableBackground|end|exponent|externalResourcesRequired|fill|fillOpacity|fillRule|filter|filterRes|filterUnits|floodColor|floodOpacity|focusable|fontFamily|fontSize|fontSizeAdjust|fontStretch|fontStyle|fontVariant|fontWeight|format|from|fr|fx|fy|g1|g2|glyphName|glyphOrientationHorizontal|glyphOrientationVertical|glyphRef|gradientTransform|gradientUnits|hanging|horizAdvX|horizOriginX|ideographic|imageRendering|in|in2|intercept|k|k1|k2|k3|k4|kernelMatrix|kernelUnitLength|kerning|keyPoints|keySplines|keyTimes|lengthAdjust|letterSpacing|lightingColor|limitingConeAngle|local|markerEnd|markerMid|markerStart|markerHeight|markerUnits|markerWidth|mask|maskContentUnits|maskUnits|mathematical|mode|numOctaves|offset|opacity|operator|order|orient|orientation|origin|overflow|overlinePosition|overlineThickness|panose1|paintOrder|pathLength|patternContentUnits|patternTransform|patternUnits|pointerEvents|points|pointsAtX|pointsAtY|pointsAtZ|preserveAlpha|preserveAspectRatio|primitiveUnits|r|radius|refX|refY|renderingIntent|repeatCount|repeatDur|requiredExtensions|requiredFeatures|restart|result|rotate|rx|ry|scale|seed|shapeRendering|slope|spacing|specularConstant|specularExponent|speed|spreadMethod|startOffset|stdDeviation|stemh|stemv|stitchTiles|stopColor|stopOpacity|strikethroughPosition|strikethroughThickness|string|stroke|strokeDasharray|strokeDashoffset|strokeLinecap|strokeLinejoin|strokeMiterlimit|strokeOpacity|strokeWidth|surfaceScale|systemLanguage|tableValues|targetX|targetY|textAnchor|textDecoration|textRendering|textLength|to|transform|u1|u2|underlinePosition|underlineThickness|unicode|unicodeBidi|unicodeRange|unitsPerEm|vAlphabetic|vHanging|vIdeographic|vMathematical|values|vectorEffect|version|vertAdvY|vertOriginX|vertOriginY|viewBox|viewTarget|visibility|widths|wordSpacing|writingMode|x|xHeight|x1|x2|xChannelSelector|xlinkActuate|xlinkArcrole|xlinkHref|xlinkRole|xlinkShow|xlinkTitle|xlinkType|xmlBase|xmlns|xmlnsXlink|xmlLang|xmlSpace|y|y1|y2|yChannelSelector|z|zoomAndPan|for|class|autofocus)|(([Dd][Aa][Tt][Aa]|[Aa][Rr][Ii][Aa]|x)-.*))$/, BM = /* @__PURE__ */ gw(
  function(u) {
    return VM.test(u) || u.charCodeAt(0) === 111 && u.charCodeAt(1) === 110 && u.charCodeAt(2) < 91;
  }
  /* Z+1 */
), IM = BM, YM = function(f) {
  return f !== "theme";
}, FR = function(f) {
  return typeof f == "string" && // 96 is one less than the char code
  // for "a" so this is checking that
  // it's a lowercase character
  f.charCodeAt(0) > 96 ? IM : YM;
}, jR = function(f, v, y) {
  var S;
  if (v) {
    var T = v.shouldForwardProp;
    S = f.__emotion_forwardProp && T ? function(_) {
      return f.__emotion_forwardProp(_) && T(_);
    } : T;
  }
  return typeof S != "function" && y && (S = f.__emotion_forwardProp), S;
}, WM = function(f) {
  var v = f.cache, y = f.serialized, S = f.isStringTag;
  return Ew(v, y, S), FM(function() {
    return NM(v, y, S);
  }), null;
}, GM = function u(f, v) {
  var y = f.__emotion_real === f, S = y && f.__emotion_base || f, T, _;
  v !== void 0 && (T = v.label, _ = v.target);
  var g = jR(f, v, y), L = g || FR(S), z = !L("as");
  return function() {
    var A = arguments, F = y && f.__emotion_styles !== void 0 ? f.__emotion_styles.slice(0) : [];
    if (T !== void 0 && F.push("label:" + T + ";"), A[0] == null || A[0].raw === void 0)
      F.push.apply(F, A);
    else {
      var U = A[0];
      F.push(U[0]);
      for (var te = A.length, B = 1; B < te; B++)
        F.push(A[B], U[B]);
    }
    var M = jM(function(j, ce, De) {
      var de = z && j.as || S, ue = "", q = [], se = j;
      if (j.theme == null) {
        se = {};
        for (var Ce in j)
          se[Ce] = j[Ce];
        se.theme = Vt.useContext(HM);
      }
      typeof j.className == "string" ? ue = DM(ce.registered, q, j.className) : j.className != null && (ue = j.className + " ");
      var Ge = bw(F.concat(q), ce.registered, se);
      ue += ce.key + "-" + Ge.name, _ !== void 0 && (ue += " " + _);
      var _t = z && g === void 0 ? FR(de) : L, x = {};
      for (var ge in j)
        z && ge === "as" || _t(ge) && (x[ge] = j[ge]);
      return x.className = ue, De && (x.ref = De), /* @__PURE__ */ Vt.createElement(Vt.Fragment, null, /* @__PURE__ */ Vt.createElement(WM, {
        cache: ce,
        serialized: Ge,
        isStringTag: typeof de == "string"
      }), /* @__PURE__ */ Vt.createElement(de, x));
    });
    return M.displayName = T !== void 0 ? T : "Styled(" + (typeof S == "string" ? S : S.displayName || S.name || "Component") + ")", M.defaultProps = f.defaultProps, M.__emotion_real = M, M.__emotion_base = S, M.__emotion_styles = F, M.__emotion_forwardProp = g, Object.defineProperty(M, "toString", {
      value: function() {
        return "." + _;
      }
    }), M.withComponent = function(j, ce) {
      var De = u(j, lC({}, v, ce, {
        shouldForwardProp: jR(M, ce, !0)
      }));
      return De.apply(void 0, F);
    }, M;
  };
}, QM = [
  "a",
  "abbr",
  "address",
  "area",
  "article",
  "aside",
  "audio",
  "b",
  "base",
  "bdi",
  "bdo",
  "big",
  "blockquote",
  "body",
  "br",
  "button",
  "canvas",
  "caption",
  "cite",
  "code",
  "col",
  "colgroup",
  "data",
  "datalist",
  "dd",
  "del",
  "details",
  "dfn",
  "dialog",
  "div",
  "dl",
  "dt",
  "em",
  "embed",
  "fieldset",
  "figcaption",
  "figure",
  "footer",
  "form",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "head",
  "header",
  "hgroup",
  "hr",
  "html",
  "i",
  "iframe",
  "img",
  "input",
  "ins",
  "kbd",
  "keygen",
  "label",
  "legend",
  "li",
  "link",
  "main",
  "map",
  "mark",
  "marquee",
  "menu",
  "menuitem",
  "meta",
  "meter",
  "nav",
  "noscript",
  "object",
  "ol",
  "optgroup",
  "option",
  "output",
  "p",
  "param",
  "picture",
  "pre",
  "progress",
  "q",
  "rp",
  "rt",
  "ruby",
  "s",
  "samp",
  "script",
  "section",
  "select",
  "small",
  "source",
  "span",
  "strong",
  "style",
  "sub",
  "summary",
  "sup",
  "table",
  "tbody",
  "td",
  "textarea",
  "tfoot",
  "th",
  "thead",
  "time",
  "title",
  "tr",
  "track",
  "u",
  "ul",
  "var",
  "video",
  "wbr",
  // SVG
  "circle",
  "clipPath",
  "defs",
  "ellipse",
  "foreignObject",
  "g",
  "image",
  "line",
  "linearGradient",
  "mask",
  "path",
  "pattern",
  "polygon",
  "polyline",
  "radialGradient",
  "rect",
  "stop",
  "svg",
  "text",
  "tspan"
], cC = GM.bind(null);
QM.forEach(function(u) {
  cC[u] = cC(u);
});
var fC = { exports: {} }, Iv = {};
/**
 * @license React
 * react-jsx-runtime.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var HR;
function qM() {
  if (HR) return Iv;
  HR = 1;
  var u = Vt, f = Symbol.for("react.element"), v = Symbol.for("react.fragment"), y = Object.prototype.hasOwnProperty, S = u.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner, T = { key: !0, ref: !0, __self: !0, __source: !0 };
  function _(g, L, z) {
    var A, F = {}, U = null, te = null;
    z !== void 0 && (U = "" + z), L.key !== void 0 && (U = "" + L.key), L.ref !== void 0 && (te = L.ref);
    for (A in L) y.call(L, A) && !T.hasOwnProperty(A) && (F[A] = L[A]);
    if (g && g.defaultProps) for (A in L = g.defaultProps, L) F[A] === void 0 && (F[A] = L[A]);
    return { $$typeof: f, type: g, key: U, ref: te, props: F, _owner: S.current };
  }
  return Iv.Fragment = v, Iv.jsx = _, Iv.jsxs = _, Iv;
}
var Yv = {}, VR;
function KM() {
  if (VR) return Yv;
  VR = 1;
  var u = {};
  /**
   * @license React
   * react-jsx-runtime.development.js
   *
   * Copyright (c) Facebook, Inc. and its affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   */
  return u.NODE_ENV !== "production" && function() {
    var f = Vt, v = Symbol.for("react.element"), y = Symbol.for("react.portal"), S = Symbol.for("react.fragment"), T = Symbol.for("react.strict_mode"), _ = Symbol.for("react.profiler"), g = Symbol.for("react.provider"), L = Symbol.for("react.context"), z = Symbol.for("react.forward_ref"), A = Symbol.for("react.suspense"), F = Symbol.for("react.suspense_list"), U = Symbol.for("react.memo"), te = Symbol.for("react.lazy"), B = Symbol.for("react.offscreen"), M = Symbol.iterator, j = "@@iterator";
    function ce(N) {
      if (N === null || typeof N != "object")
        return null;
      var fe = M && N[M] || N[j];
      return typeof fe == "function" ? fe : null;
    }
    var De = f.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
    function de(N) {
      {
        for (var fe = arguments.length, Ae = new Array(fe > 1 ? fe - 1 : 0), Ue = 1; Ue < fe; Ue++)
          Ae[Ue - 1] = arguments[Ue];
        ue("error", N, Ae);
      }
    }
    function ue(N, fe, Ae) {
      {
        var Ue = De.ReactDebugCurrentFrame, kt = Ue.getStackAddendum();
        kt !== "" && (fe += "%s", Ae = Ae.concat([kt]));
        var yt = Ae.map(function(Nt) {
          return String(Nt);
        });
        yt.unshift("Warning: " + fe), Function.prototype.apply.call(console[N], console, yt);
      }
    }
    var q = !1, se = !1, Ce = !1, Ge = !1, _t = !1, x;
    x = Symbol.for("react.module.reference");
    function ge(N) {
      return !!(typeof N == "string" || typeof N == "function" || N === S || N === _ || _t || N === T || N === A || N === F || Ge || N === B || q || se || Ce || typeof N == "object" && N !== null && (N.$$typeof === te || N.$$typeof === U || N.$$typeof === g || N.$$typeof === L || N.$$typeof === z || // This needs to include all possible module reference object
      // types supported by any Flight configuration anywhere since
      // we don't know which Flight build this will end up being used
      // with.
      N.$$typeof === x || N.getModuleId !== void 0));
    }
    function je(N, fe, Ae) {
      var Ue = N.displayName;
      if (Ue)
        return Ue;
      var kt = fe.displayName || fe.name || "";
      return kt !== "" ? Ae + "(" + kt + ")" : Ae;
    }
    function Qe(N) {
      return N.displayName || "Context";
    }
    function Pe(N) {
      if (N == null)
        return null;
      if (typeof N.tag == "number" && de("Received an unexpected object in getComponentNameFromType(). This is likely a bug in React. Please file an issue."), typeof N == "function")
        return N.displayName || N.name || null;
      if (typeof N == "string")
        return N;
      switch (N) {
        case S:
          return "Fragment";
        case y:
          return "Portal";
        case _:
          return "Profiler";
        case T:
          return "StrictMode";
        case A:
          return "Suspense";
        case F:
          return "SuspenseList";
      }
      if (typeof N == "object")
        switch (N.$$typeof) {
          case L:
            var fe = N;
            return Qe(fe) + ".Consumer";
          case g:
            var Ae = N;
            return Qe(Ae._context) + ".Provider";
          case z:
            return je(N, N.render, "ForwardRef");
          case U:
            var Ue = N.displayName || null;
            return Ue !== null ? Ue : Pe(N.type) || "Memo";
          case te: {
            var kt = N, yt = kt._payload, Nt = kt._init;
            try {
              return Pe(Nt(yt));
            } catch {
              return null;
            }
          }
        }
      return null;
    }
    var pt = Object.assign, vt = 0, ot, ie, Ie, ke, k, I, ye;
    function Re() {
    }
    Re.__reactDisabledLog = !0;
    function be() {
      {
        if (vt === 0) {
          ot = console.log, ie = console.info, Ie = console.warn, ke = console.error, k = console.group, I = console.groupCollapsed, ye = console.groupEnd;
          var N = {
            configurable: !0,
            enumerable: !0,
            value: Re,
            writable: !0
          };
          Object.defineProperties(console, {
            info: N,
            log: N,
            warn: N,
            error: N,
            group: N,
            groupCollapsed: N,
            groupEnd: N
          });
        }
        vt++;
      }
    }
    function Le() {
      {
        if (vt--, vt === 0) {
          var N = {
            configurable: !0,
            enumerable: !0,
            writable: !0
          };
          Object.defineProperties(console, {
            log: pt({}, N, {
              value: ot
            }),
            info: pt({}, N, {
              value: ie
            }),
            warn: pt({}, N, {
              value: Ie
            }),
            error: pt({}, N, {
              value: ke
            }),
            group: pt({}, N, {
              value: k
            }),
            groupCollapsed: pt({}, N, {
              value: I
            }),
            groupEnd: pt({}, N, {
              value: ye
            })
          });
        }
        vt < 0 && de("disabledDepth fell below zero. This is a bug in React. Please file an issue.");
      }
    }
    var ze = De.ReactCurrentDispatcher, we;
    function Ye(N, fe, Ae) {
      {
        if (we === void 0)
          try {
            throw Error();
          } catch (kt) {
            var Ue = kt.stack.trim().match(/\n( *(at )?)/);
            we = Ue && Ue[1] || "";
          }
        return `
` + we + N;
      }
    }
    var et = !1, ut;
    {
      var Ht = typeof WeakMap == "function" ? WeakMap : Map;
      ut = new Ht();
    }
    function Te(N, fe) {
      if (!N || et)
        return "";
      {
        var Ae = ut.get(N);
        if (Ae !== void 0)
          return Ae;
      }
      var Ue;
      et = !0;
      var kt = Error.prepareStackTrace;
      Error.prepareStackTrace = void 0;
      var yt;
      yt = ze.current, ze.current = null, be();
      try {
        if (fe) {
          var Nt = function() {
            throw Error();
          };
          if (Object.defineProperty(Nt.prototype, "props", {
            set: function() {
              throw Error();
            }
          }), typeof Reflect == "object" && Reflect.construct) {
            try {
              Reflect.construct(Nt, []);
            } catch (Dn) {
              Ue = Dn;
            }
            Reflect.construct(N, [], Nt);
          } else {
            try {
              Nt.call();
            } catch (Dn) {
              Ue = Dn;
            }
            N.call(Nt.prototype);
          }
        } else {
          try {
            throw Error();
          } catch (Dn) {
            Ue = Dn;
          }
          N();
        }
      } catch (Dn) {
        if (Dn && Ue && typeof Dn.stack == "string") {
          for (var wt = Dn.stack.split(`
`), jn = Ue.stack.split(`
`), Sn = wt.length - 1, wn = jn.length - 1; Sn >= 1 && wn >= 0 && wt[Sn] !== jn[wn]; )
            wn--;
          for (; Sn >= 1 && wn >= 0; Sn--, wn--)
            if (wt[Sn] !== jn[wn]) {
              if (Sn !== 1 || wn !== 1)
                do
                  if (Sn--, wn--, wn < 0 || wt[Sn] !== jn[wn]) {
                    var $r = `
` + wt[Sn].replace(" at new ", " at ");
                    return N.displayName && $r.includes("<anonymous>") && ($r = $r.replace("<anonymous>", N.displayName)), typeof N == "function" && ut.set(N, $r), $r;
                  }
                while (Sn >= 1 && wn >= 0);
              break;
            }
        }
      } finally {
        et = !1, ze.current = yt, Le(), Error.prepareStackTrace = kt;
      }
      var vi = N ? N.displayName || N.name : "", qt = vi ? Ye(vi) : "";
      return typeof N == "function" && ut.set(N, qt), qt;
    }
    function Wt(N, fe, Ae) {
      return Te(N, !1);
    }
    function Fn(N) {
      var fe = N.prototype;
      return !!(fe && fe.isReactComponent);
    }
    function Ln(N, fe, Ae) {
      if (N == null)
        return "";
      if (typeof N == "function")
        return Te(N, Fn(N));
      if (typeof N == "string")
        return Ye(N);
      switch (N) {
        case A:
          return Ye("Suspense");
        case F:
          return Ye("SuspenseList");
      }
      if (typeof N == "object")
        switch (N.$$typeof) {
          case z:
            return Wt(N.render);
          case U:
            return Ln(N.type, fe, Ae);
          case te: {
            var Ue = N, kt = Ue._payload, yt = Ue._init;
            try {
              return Ln(yt(kt), fe, Ae);
            } catch {
            }
          }
        }
      return "";
    }
    var Gn = Object.prototype.hasOwnProperty, _a = {}, di = De.ReactDebugCurrentFrame;
    function Ir(N) {
      if (N) {
        var fe = N._owner, Ae = Ln(N.type, N._source, fe ? fe.type : null);
        di.setExtraStackFrame(Ae);
      } else
        di.setExtraStackFrame(null);
    }
    function ir(N, fe, Ae, Ue, kt) {
      {
        var yt = Function.call.bind(Gn);
        for (var Nt in N)
          if (yt(N, Nt)) {
            var wt = void 0;
            try {
              if (typeof N[Nt] != "function") {
                var jn = Error((Ue || "React class") + ": " + Ae + " type `" + Nt + "` is invalid; it must be a function, usually from the `prop-types` package, but received `" + typeof N[Nt] + "`.This often happens because of typos such as `PropTypes.function` instead of `PropTypes.func`.");
                throw jn.name = "Invariant Violation", jn;
              }
              wt = N[Nt](fe, Nt, Ue, Ae, null, "SECRET_DO_NOT_PASS_THIS_OR_YOU_WILL_BE_FIRED");
            } catch (Sn) {
              wt = Sn;
            }
            wt && !(wt instanceof Error) && (Ir(kt), de("%s: type specification of %s `%s` is invalid; the type checker function must return `null` or an `Error` but returned a %s. You may have forgotten to pass an argument to the type checker creator (arrayOf, instanceOf, objectOf, oneOf, oneOfType, and shape all require an argument).", Ue || "React class", Ae, Nt, typeof wt), Ir(null)), wt instanceof Error && !(wt.message in _a) && (_a[wt.message] = !0, Ir(kt), de("Failed %s type: %s", Ae, wt.message), Ir(null));
          }
      }
    }
    var dr = Array.isArray;
    function pr(N) {
      return dr(N);
    }
    function Pr(N) {
      {
        var fe = typeof Symbol == "function" && Symbol.toStringTag, Ae = fe && N[Symbol.toStringTag] || N.constructor.name || "Object";
        return Ae;
      }
    }
    function pi(N) {
      try {
        return Qn(N), !1;
      } catch {
        return !0;
      }
    }
    function Qn(N) {
      return "" + N;
    }
    function br(N) {
      if (pi(N))
        return de("The provided key is an unsupported type %s. This value must be coerced to a string before before using it here.", Pr(N)), Qn(N);
    }
    var la = De.ReactCurrentOwner, eo = {
      key: !0,
      ref: !0,
      __self: !0,
      __source: !0
    }, ka, xe;
    function it(N) {
      if (Gn.call(N, "ref")) {
        var fe = Object.getOwnPropertyDescriptor(N, "ref").get;
        if (fe && fe.isReactWarning)
          return !1;
      }
      return N.ref !== void 0;
    }
    function Rt(N) {
      if (Gn.call(N, "key")) {
        var fe = Object.getOwnPropertyDescriptor(N, "key").get;
        if (fe && fe.isReactWarning)
          return !1;
      }
      return N.key !== void 0;
    }
    function Gt(N, fe) {
      typeof N.ref == "string" && la.current;
    }
    function bn(N, fe) {
      {
        var Ae = function() {
          ka || (ka = !0, de("%s: `key` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://reactjs.org/link/special-props)", fe));
        };
        Ae.isReactWarning = !0, Object.defineProperty(N, "key", {
          get: Ae,
          configurable: !0
        });
      }
    }
    function Tn(N, fe) {
      {
        var Ae = function() {
          xe || (xe = !0, de("%s: `ref` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://reactjs.org/link/special-props)", fe));
        };
        Ae.isReactWarning = !0, Object.defineProperty(N, "ref", {
          get: Ae,
          configurable: !0
        });
      }
    }
    var Rn = function(N, fe, Ae, Ue, kt, yt, Nt) {
      var wt = {
        // This tag allows us to uniquely identify this as a React Element
        $$typeof: v,
        // Built-in properties that belong on the element
        type: N,
        key: fe,
        ref: Ae,
        props: Nt,
        // Record the component responsible for creating this element.
        _owner: yt
      };
      return wt._store = {}, Object.defineProperty(wt._store, "validated", {
        configurable: !1,
        enumerable: !1,
        writable: !0,
        value: !1
      }), Object.defineProperty(wt, "_self", {
        configurable: !1,
        enumerable: !1,
        writable: !1,
        value: Ue
      }), Object.defineProperty(wt, "_source", {
        configurable: !1,
        enumerable: !1,
        writable: !1,
        value: kt
      }), Object.freeze && (Object.freeze(wt.props), Object.freeze(wt)), wt;
    };
    function vr(N, fe, Ae, Ue, kt) {
      {
        var yt, Nt = {}, wt = null, jn = null;
        Ae !== void 0 && (br(Ae), wt = "" + Ae), Rt(fe) && (br(fe.key), wt = "" + fe.key), it(fe) && (jn = fe.ref, Gt(fe, kt));
        for (yt in fe)
          Gn.call(fe, yt) && !eo.hasOwnProperty(yt) && (Nt[yt] = fe[yt]);
        if (N && N.defaultProps) {
          var Sn = N.defaultProps;
          for (yt in Sn)
            Nt[yt] === void 0 && (Nt[yt] = Sn[yt]);
        }
        if (wt || jn) {
          var wn = typeof N == "function" ? N.displayName || N.name || "Unknown" : N;
          wt && bn(Nt, wn), jn && Tn(Nt, wn);
        }
        return Rn(N, wt, jn, kt, Ue, la.current, Nt);
      }
    }
    var gn = De.ReactCurrentOwner, an = De.ReactDebugCurrentFrame;
    function Qt(N) {
      if (N) {
        var fe = N._owner, Ae = Ln(N.type, N._source, fe ? fe.type : null);
        an.setExtraStackFrame(Ae);
      } else
        an.setExtraStackFrame(null);
    }
    var Oa;
    Oa = !1;
    function Ia(N) {
      return typeof N == "object" && N !== null && N.$$typeof === v;
    }
    function Ya() {
      {
        if (gn.current) {
          var N = Pe(gn.current.type);
          if (N)
            return `

Check the render method of \`` + N + "`.";
        }
        return "";
      }
    }
    function to(N) {
      return "";
    }
    var Sl = {};
    function El(N) {
      {
        var fe = Ya();
        if (!fe) {
          var Ae = typeof N == "string" ? N : N.displayName || N.name;
          Ae && (fe = `

Check the top-level render call using <` + Ae + ">.");
        }
        return fe;
      }
    }
    function no(N, fe) {
      {
        if (!N._store || N._store.validated || N.key != null)
          return;
        N._store.validated = !0;
        var Ae = El(fe);
        if (Sl[Ae])
          return;
        Sl[Ae] = !0;
        var Ue = "";
        N && N._owner && N._owner !== gn.current && (Ue = " It was passed a child from " + Pe(N._owner.type) + "."), Qt(N), de('Each child in a list should have a unique "key" prop.%s%s See https://reactjs.org/link/warning-keys for more information.', Ae, Ue), Qt(null);
      }
    }
    function Cl(N, fe) {
      {
        if (typeof N != "object")
          return;
        if (pr(N))
          for (var Ae = 0; Ae < N.length; Ae++) {
            var Ue = N[Ae];
            Ia(Ue) && no(Ue, fe);
          }
        else if (Ia(N))
          N._store && (N._store.validated = !0);
        else if (N) {
          var kt = ce(N);
          if (typeof kt == "function" && kt !== N.entries)
            for (var yt = kt.call(N), Nt; !(Nt = yt.next()).done; )
              Ia(Nt.value) && no(Nt.value, fe);
        }
      }
    }
    function Di(N) {
      {
        var fe = N.type;
        if (fe == null || typeof fe == "string")
          return;
        var Ae;
        if (typeof fe == "function")
          Ae = fe.propTypes;
        else if (typeof fe == "object" && (fe.$$typeof === z || // Note: Memo only checks outer props here.
        // Inner props are checked in the reconciler.
        fe.$$typeof === U))
          Ae = fe.propTypes;
        else
          return;
        if (Ae) {
          var Ue = Pe(fe);
          ir(Ae, N.props, "prop", Ue, N);
        } else if (fe.PropTypes !== void 0 && !Oa) {
          Oa = !0;
          var kt = Pe(fe);
          de("Component %s declared `PropTypes` instead of `propTypes`. Did you misspell the property assignment?", kt || "Unknown");
        }
        typeof fe.getDefaultProps == "function" && !fe.getDefaultProps.isReactClassApproved && de("getDefaultProps is only used on classic React.createClass definitions. Use a static property named `defaultProps` instead.");
      }
    }
    function Da(N) {
      {
        for (var fe = Object.keys(N.props), Ae = 0; Ae < fe.length; Ae++) {
          var Ue = fe[Ae];
          if (Ue !== "children" && Ue !== "key") {
            Qt(N), de("Invalid prop `%s` supplied to `React.Fragment`. React.Fragment can only have `key` and `children` props.", Ue), Qt(null);
            break;
          }
        }
        N.ref !== null && (Qt(N), de("Invalid attribute `ref` supplied to `React.Fragment`."), Qt(null));
      }
    }
    var Tr = {};
    function Na(N, fe, Ae, Ue, kt, yt) {
      {
        var Nt = ge(N);
        if (!Nt) {
          var wt = "";
          (N === void 0 || typeof N == "object" && N !== null && Object.keys(N).length === 0) && (wt += " You likely forgot to export your component from the file it's defined in, or you might have mixed up default and named imports.");
          var jn = to();
          jn ? wt += jn : wt += Ya();
          var Sn;
          N === null ? Sn = "null" : pr(N) ? Sn = "array" : N !== void 0 && N.$$typeof === v ? (Sn = "<" + (Pe(N.type) || "Unknown") + " />", wt = " Did you accidentally export a JSX literal instead of a component?") : Sn = typeof N, de("React.jsx: type is invalid -- expected a string (for built-in components) or a class/function (for composite components) but got: %s.%s", Sn, wt);
        }
        var wn = vr(N, fe, Ae, kt, yt);
        if (wn == null)
          return wn;
        if (Nt) {
          var $r = fe.children;
          if ($r !== void 0)
            if (Ue)
              if (pr($r)) {
                for (var vi = 0; vi < $r.length; vi++)
                  Cl($r[vi], N);
                Object.freeze && Object.freeze($r);
              } else
                de("React.jsx: Static children should always be an array. You are likely explicitly calling React.jsxs or React.jsxDEV. Use the Babel transform instead.");
            else
              Cl($r, N);
        }
        if (Gn.call(fe, "key")) {
          var qt = Pe(N), Dn = Object.keys(fe).filter(function(ao) {
            return ao !== "key";
          }), Et = Dn.length > 0 ? "{key: someKey, " + Dn.join(": ..., ") + ": ...}" : "{key: someKey}";
          if (!Tr[qt + Et]) {
            var Mi = Dn.length > 0 ? "{" + Dn.join(": ..., ") + ": ...}" : "{}";
            de(`A props object containing a "key" prop is being spread into JSX:
  let props = %s;
  <%s {...props} />
React keys must be passed directly to JSX without using spread:
  let props = %s;
  <%s key={someKey} {...props} />`, Et, qt, Mi, qt), Tr[qt + Et] = !0;
          }
        }
        return N === S ? Da(wn) : Di(wn), wn;
      }
    }
    function ua(N, fe, Ae) {
      return Na(N, fe, Ae, !0);
    }
    function Ni(N, fe, Ae) {
      return Na(N, fe, Ae, !1);
    }
    var Ai = Ni, ro = ua;
    Yv.Fragment = S, Yv.jsx = Ai, Yv.jsxs = ro;
  }(), Yv;
}
var XM = {};
XM.NODE_ENV === "production" ? fC.exports = qM() : fC.exports = KM();
var jd = fC.exports, JM = {};
function ZM(u, f) {
  const v = cC(u, f);
  return JM.NODE_ENV !== "production" ? (...y) => {
    const S = typeof u == "string" ? `"${u}"` : "component";
    return y.length === 0 ? console.error([`MUI: Seems like you called \`styled(${S})()\` without a \`style\` argument.`, 'You must provide a `styles` argument: `styled("div")(styleYouForgotToPass)`.'].join(`
`)) : y.some((T) => T === void 0) && console.error(`MUI: the styled(${S})(...args) API requires all its args to be defined.`), v(...y);
  } : v;
}
function eL(u, f) {
  Array.isArray(u.__emotion_styles) && (u.__emotion_styles = f(u.__emotion_styles));
}
const BR = [];
function IR(u) {
  return BR[0] = u, bw(BR);
}
const tL = (u) => {
  const f = Object.keys(u).map((v) => ({
    key: v,
    val: u[v]
  })) || [];
  return f.sort((v, y) => v.val - y.val), f.reduce((v, y) => ({
    ...v,
    [y.key]: y.val
  }), {});
};
function nL(u) {
  const {
    // The breakpoint **start** at this value.
    // For instance with the first breakpoint xs: [xs, sm).
    values: f = {
      xs: 0,
      // phone
      sm: 600,
      // tablet
      md: 900,
      // small laptop
      lg: 1200,
      // desktop
      xl: 1536
      // large screen
    },
    unit: v = "px",
    step: y = 5,
    ...S
  } = u, T = tL(f), _ = Object.keys(T);
  function g(U) {
    return `@media (min-width:${typeof f[U] == "number" ? f[U] : U}${v})`;
  }
  function L(U) {
    return `@media (max-width:${(typeof f[U] == "number" ? f[U] : U) - y / 100}${v})`;
  }
  function z(U, te) {
    const B = _.indexOf(te);
    return `@media (min-width:${typeof f[U] == "number" ? f[U] : U}${v}) and (max-width:${(B !== -1 && typeof f[_[B]] == "number" ? f[_[B]] : te) - y / 100}${v})`;
  }
  function A(U) {
    return _.indexOf(U) + 1 < _.length ? z(U, _[_.indexOf(U) + 1]) : g(U);
  }
  function F(U) {
    const te = _.indexOf(U);
    return te === 0 ? g(_[1]) : te === _.length - 1 ? L(_[te]) : z(U, _[_.indexOf(U) + 1]).replace("@media", "@media not all and");
  }
  return {
    keys: _,
    values: T,
    up: g,
    down: L,
    between: z,
    only: A,
    not: F,
    unit: v,
    ...S
  };
}
const rL = {
  borderRadius: 4
};
var aL = {};
function Rw(u = 8, f = mC({
  spacing: u
})) {
  if (u.mui)
    return u;
  const v = (...y) => (aL.NODE_ENV !== "production" && (y.length <= 4 || console.error(`MUI: Too many arguments provided, expected between 0 and 4, got ${y.length}`)), (y.length === 0 ? [1] : y).map((T) => {
    const _ = f(T);
    return typeof _ == "number" ? `${_}px` : _;
  }).join(" "));
  return v.mui = !0, v;
}
function iL(u, f) {
  var y;
  const v = this;
  if (v.vars) {
    if (!((y = v.colorSchemes) != null && y[u]) || typeof v.getColorSchemeSelector != "function")
      return {};
    let S = v.getColorSchemeSelector(u);
    return S === "&" ? f : ((S.includes("data-") || S.includes(".")) && (S = `*:where(${S.replace(/\s*&$/, "")}) &`), {
      [S]: f
    });
  }
  return v.palette.mode === u ? f : {};
}
function ww(u = {}, ...f) {
  const {
    breakpoints: v = {},
    palette: y = {},
    spacing: S,
    shape: T = {},
    ..._
  } = u, g = nL(v), L = Rw(S);
  let z = ki({
    breakpoints: g,
    direction: "ltr",
    components: {},
    // Inject component definitions.
    palette: {
      mode: "light",
      ...y
    },
    spacing: L,
    shape: {
      ...rL,
      ...T
    }
  }, _);
  return z = lA(z), z.applyStyles = iL, z = f.reduce((A, F) => ki(A, F), z), z.unstable_sxConfig = {
    ...Eg,
    ..._ == null ? void 0 : _.unstable_sxConfig
  }, z.unstable_sx = function(F) {
    return $d({
      sx: F,
      theme: this
    });
  }, z;
}
function xw(u) {
  const {
    variants: f,
    ...v
  } = u, y = {
    variants: f,
    style: IR(v),
    isProcessed: !0
  };
  return y.style === v || f && f.forEach((S) => {
    typeof S.style != "function" && (S.style = IR(S.style));
  }), y;
}
var _w = {};
const oL = ww();
function XE(u) {
  return u !== "ownerState" && u !== "theme" && u !== "sx" && u !== "as";
}
function lL(u) {
  return u ? (f, v) => v[u] : null;
}
function uL(u, f, v) {
  u.theme = dL(u.theme) ? v : u.theme[f] || u.theme;
}
function og(u, f) {
  const v = typeof f == "function" ? f(u) : f;
  if (Array.isArray(v))
    return v.flatMap((y) => og(u, y));
  if (Array.isArray(v == null ? void 0 : v.variants)) {
    let y;
    if (v.isProcessed)
      y = v.style;
    else {
      const {
        variants: S,
        ...T
      } = v;
      y = T;
    }
    return kw(u, v.variants, [y]);
  }
  return v != null && v.isProcessed ? v.style : v;
}
function kw(u, f, v = []) {
  var S;
  let y;
  e: for (let T = 0; T < f.length; T += 1) {
    const _ = f[T];
    if (typeof _.props == "function") {
      if (y ?? (y = {
        ...u,
        ...u.ownerState,
        ownerState: u.ownerState
      }), !_.props(y))
        continue;
    } else
      for (const g in _.props)
        if (u[g] !== _.props[g] && ((S = u.ownerState) == null ? void 0 : S[g]) !== _.props[g])
          continue e;
    typeof _.style == "function" ? (y ?? (y = {
      ...u,
      ...u.ownerState,
      ownerState: u.ownerState
    }), v.push(_.style(y))) : v.push(_.style);
  }
  return v;
}
function sL(u = {}) {
  const {
    themeId: f,
    defaultTheme: v = oL,
    rootShouldForwardProp: y = XE,
    slotShouldForwardProp: S = XE
  } = u;
  function T(g) {
    uL(g, f, v);
  }
  return (g, L = {}) => {
    eL(g, (q) => q.filter((se) => se !== $d));
    const {
      name: z,
      slot: A,
      skipVariantsResolver: F,
      skipSx: U,
      // TODO v6: remove `lowercaseFirstLetter()` in the next major release
      // For more details: https://github.com/mui/material-ui/pull/37908
      overridesResolver: te = lL(Ow(A)),
      ...B
    } = L, M = F !== void 0 ? F : (
      // TODO v6: remove `Root` in the next major release
      // For more details: https://github.com/mui/material-ui/pull/37908
      A && A !== "Root" && A !== "root" || !1
    ), j = U || !1;
    let ce = XE;
    A === "Root" || A === "root" ? ce = y : A ? ce = S : pL(g) && (ce = void 0);
    const De = ZM(g, {
      shouldForwardProp: ce,
      label: fL(z, A),
      ...B
    }), de = (q) => {
      if (typeof q == "function" && q.__emotion_real !== q)
        return function(Ce) {
          return og(Ce, q);
        };
      if (pu(q)) {
        const se = xw(q);
        return se.variants ? function(Ge) {
          return og(Ge, se);
        } : se.style;
      }
      return q;
    }, ue = (...q) => {
      const se = [], Ce = q.map(de), Ge = [];
      if (se.push(T), z && te && Ge.push(function(je) {
        var vt, ot;
        const Pe = (ot = (vt = je.theme.components) == null ? void 0 : vt[z]) == null ? void 0 : ot.styleOverrides;
        if (!Pe)
          return null;
        const pt = {};
        for (const ie in Pe)
          pt[ie] = og(je, Pe[ie]);
        return te(je, pt);
      }), z && !M && Ge.push(function(je) {
        var pt, vt;
        const Qe = je.theme, Pe = (vt = (pt = Qe == null ? void 0 : Qe.components) == null ? void 0 : pt[z]) == null ? void 0 : vt.variants;
        return Pe ? kw(je, Pe) : null;
      }), j || Ge.push($d), Array.isArray(Ce[0])) {
        const ge = Ce.shift(), je = new Array(se.length).fill(""), Qe = new Array(Ge.length).fill("");
        let Pe;
        Pe = [...je, ...ge, ...Qe], Pe.raw = [...je, ...ge.raw, ...Qe], se.unshift(Pe);
      }
      const _t = [...se, ...Ce, ...Ge], x = De(..._t);
      return g.muiName && (x.muiName = g.muiName), _w.NODE_ENV !== "production" && (x.displayName = cL(z, A, g)), x;
    };
    return De.withConfig && (ue.withConfig = De.withConfig), ue;
  };
}
function cL(u, f, v) {
  return u ? `${u}${Fc(f || "")}` : `Styled(${QN(v)})`;
}
function fL(u, f) {
  let v;
  return _w.NODE_ENV !== "production" && u && (v = `${u}-${Ow(f || "Root")}`), v;
}
function dL(u) {
  for (const f in u)
    return !1;
  return !0;
}
function pL(u) {
  return typeof u == "string" && // 96 is one less than the char code
  // for "a" so this is checking that
  // it's a lowercase character
  u.charCodeAt(0) > 96;
}
function Ow(u) {
  return u && u.charAt(0).toLowerCase() + u.slice(1);
}
var eh = {};
function bC(u, f = 0, v = 1) {
  return eh.NODE_ENV !== "production" && (u < f || u > v) && console.error(`MUI: The value provided ${u} is out of range [${f}, ${v}].`), tA(u, f, v);
}
function vL(u) {
  u = u.slice(1);
  const f = new RegExp(`.{1,${u.length >= 6 ? 2 : 1}}`, "g");
  let v = u.match(f);
  return v && v[0].length === 1 && (v = v.map((y) => y + y)), eh.NODE_ENV !== "production" && u.length !== u.trim().length && console.error(`MUI: The color: "${u}" is invalid. Make sure the color input doesn't contain leading/trailing space.`), v ? `rgb${v.length === 4 ? "a" : ""}(${v.map((y, S) => S < 3 ? parseInt(y, 16) : Math.round(parseInt(y, 16) / 255 * 1e3) / 1e3).join(", ")})` : "";
}
function Ss(u) {
  if (u.type)
    return u;
  if (u.charAt(0) === "#")
    return Ss(vL(u));
  const f = u.indexOf("("), v = u.substring(0, f);
  if (!["rgb", "rgba", "hsl", "hsla", "color"].includes(v))
    throw new Error(eh.NODE_ENV !== "production" ? `MUI: Unsupported \`${u}\` color.
The following formats are supported: #nnn, #nnnnnn, rgb(), rgba(), hsl(), hsla(), color().` : gs(9, u));
  let y = u.substring(f + 1, u.length - 1), S;
  if (v === "color") {
    if (y = y.split(" "), S = y.shift(), y.length === 4 && y[3].charAt(0) === "/" && (y[3] = y[3].slice(1)), !["srgb", "display-p3", "a98-rgb", "prophoto-rgb", "rec-2020"].includes(S))
      throw new Error(eh.NODE_ENV !== "production" ? `MUI: unsupported \`${S}\` color space.
The following color spaces are supported: srgb, display-p3, a98-rgb, prophoto-rgb, rec-2020.` : gs(10, S));
  } else
    y = y.split(",");
  return y = y.map((T) => parseFloat(T)), {
    type: v,
    values: y,
    colorSpace: S
  };
}
const hL = (u) => {
  const f = Ss(u);
  return f.values.slice(0, 3).map((v, y) => f.type.includes("hsl") && y !== 0 ? `${v}%` : v).join(" ");
}, Qv = (u, f) => {
  try {
    return hL(u);
  } catch {
    return f && eh.NODE_ENV !== "production" && console.warn(f), u;
  }
};
function Rg(u) {
  const {
    type: f,
    colorSpace: v
  } = u;
  let {
    values: y
  } = u;
  return f.includes("rgb") ? y = y.map((S, T) => T < 3 ? parseInt(S, 10) : S) : f.includes("hsl") && (y[1] = `${y[1]}%`, y[2] = `${y[2]}%`), f.includes("color") ? y = `${v} ${y.join(" ")}` : y = `${y.join(", ")}`, `${f}(${y})`;
}
function Dw(u) {
  u = Ss(u);
  const {
    values: f
  } = u, v = f[0], y = f[1] / 100, S = f[2] / 100, T = y * Math.min(S, 1 - S), _ = (z, A = (z + v / 30) % 12) => S - T * Math.max(Math.min(A - 3, 9 - A, 1), -1);
  let g = "rgb";
  const L = [Math.round(_(0) * 255), Math.round(_(8) * 255), Math.round(_(4) * 255)];
  return u.type === "hsla" && (g += "a", L.push(f[3])), Rg({
    type: g,
    values: L
  });
}
function dC(u) {
  u = Ss(u);
  let f = u.type === "hsl" || u.type === "hsla" ? Ss(Dw(u)).values : u.values;
  return f = f.map((v) => (u.type !== "color" && (v /= 255), v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)), Number((0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]).toFixed(3));
}
function YR(u, f) {
  const v = dC(u), y = dC(f);
  return (Math.max(v, y) + 0.05) / (Math.min(v, y) + 0.05);
}
function mL(u, f) {
  return u = Ss(u), f = bC(f), (u.type === "rgb" || u.type === "hsl") && (u.type += "a"), u.type === "color" ? u.values[3] = `/${f}` : u.values[3] = f, Rg(u);
}
function eg(u, f, v) {
  try {
    return mL(u, f);
  } catch {
    return u;
  }
}
function TC(u, f) {
  if (u = Ss(u), f = bC(f), u.type.includes("hsl"))
    u.values[2] *= 1 - f;
  else if (u.type.includes("rgb") || u.type.includes("color"))
    for (let v = 0; v < 3; v += 1)
      u.values[v] *= 1 - f;
  return Rg(u);
}
function kn(u, f, v) {
  try {
    return TC(u, f);
  } catch {
    return u;
  }
}
function RC(u, f) {
  if (u = Ss(u), f = bC(f), u.type.includes("hsl"))
    u.values[2] += (100 - u.values[2]) * f;
  else if (u.type.includes("rgb"))
    for (let v = 0; v < 3; v += 1)
      u.values[v] += (255 - u.values[v]) * f;
  else if (u.type.includes("color"))
    for (let v = 0; v < 3; v += 1)
      u.values[v] += (1 - u.values[v]) * f;
  return Rg(u);
}
function On(u, f, v) {
  try {
    return RC(u, f);
  } catch {
    return u;
  }
}
function yL(u, f = 0.15) {
  return dC(u) > 0.5 ? TC(u, f) : RC(u, f);
}
function tg(u, f, v) {
  try {
    return yL(u, f);
  } catch {
    return u;
  }
}
var gL = {};
const SL = /* @__PURE__ */ Vt.createContext(void 0);
gL.NODE_ENV !== "production" && (Zt.node, Zt.object);
function EL(u) {
  const {
    theme: f,
    name: v,
    props: y
  } = u;
  if (!f || !f.components || !f.components[v])
    return y;
  const S = f.components[v];
  return S.defaultProps ? oC(S.defaultProps, y) : !S.styleOverrides && !S.variants ? oC(S, y) : y;
}
function CL({
  props: u,
  name: f
}) {
  const v = Vt.useContext(SL);
  return EL({
    props: u,
    name: f,
    theme: {
      components: v
    }
  });
}
const WR = {
  theme: void 0
};
function bL(u) {
  let f, v;
  return function(S) {
    let T = f;
    return (T === void 0 || S.theme !== v) && (WR.theme = S.theme, T = xw(u(WR)), f = T, v = S.theme), T;
  };
}
function TL(u = "") {
  function f(...y) {
    if (!y.length)
      return "";
    const S = y[0];
    return typeof S == "string" && !S.match(/(#|\(|\)|(-?(\d*\.)?\d+)(px|em|%|ex|ch|rem|vw|vh|vmin|vmax|cm|mm|in|pt|pc))|^(-?(\d*\.)?\d+)$|(\d+ \d+ \d+)/) ? `, var(--${u ? `${u}-` : ""}${S}${f(...y.slice(1))})` : `, ${S}`;
  }
  return (y, ...S) => `var(--${u ? `${u}-` : ""}${y}${f(...S)})`;
}
const GR = (u, f, v, y = []) => {
  let S = u;
  f.forEach((T, _) => {
    _ === f.length - 1 ? Array.isArray(S) ? S[Number(T)] = v : S && typeof S == "object" && (S[T] = v) : S && typeof S == "object" && (S[T] || (S[T] = y.includes(T) ? [] : {}), S = S[T]);
  });
}, RL = (u, f, v) => {
  function y(S, T = [], _ = []) {
    Object.entries(S).forEach(([g, L]) => {
      (!v || v && !v([...T, g])) && L != null && (typeof L == "object" && Object.keys(L).length > 0 ? y(L, [...T, g], Array.isArray(L) ? [..._, g] : _) : f([...T, g], L, _));
    });
  }
  y(u);
}, wL = (u, f) => typeof f == "number" ? ["lineHeight", "fontWeight", "opacity", "zIndex"].some((y) => u.includes(y)) || u[u.length - 1].toLowerCase().includes("opacity") ? f : `${f}px` : f;
function JE(u, f) {
  const {
    prefix: v,
    shouldSkipGeneratingVar: y
  } = f || {}, S = {}, T = {}, _ = {};
  return RL(
    u,
    (g, L, z) => {
      if ((typeof L == "string" || typeof L == "number") && (!y || !y(g, L))) {
        const A = `--${v ? `${v}-` : ""}${g.join("-")}`, F = wL(g, L);
        Object.assign(S, {
          [A]: F
        }), GR(T, g, `var(${A})`, z), GR(_, g, `var(${A}, ${F})`, z);
      }
    },
    (g) => g[0] === "vars"
    // skip 'vars/*' paths
  ), {
    css: S,
    vars: T,
    varsWithDefaults: _
  };
}
function xL(u, f = {}) {
  const {
    getSelector: v = j,
    disableCssColorScheme: y,
    colorSchemeSelector: S
  } = f, {
    colorSchemes: T = {},
    components: _,
    defaultColorScheme: g = "light",
    ...L
  } = u, {
    vars: z,
    css: A,
    varsWithDefaults: F
  } = JE(L, f);
  let U = F;
  const te = {}, {
    [g]: B,
    ...M
  } = T;
  if (Object.entries(M || {}).forEach(([de, ue]) => {
    const {
      vars: q,
      css: se,
      varsWithDefaults: Ce
    } = JE(ue, f);
    U = ki(U, Ce), te[de] = {
      css: se,
      vars: q
    };
  }), B) {
    const {
      css: de,
      vars: ue,
      varsWithDefaults: q
    } = JE(B, f);
    U = ki(U, q), te[g] = {
      css: de,
      vars: ue
    };
  }
  function j(de, ue) {
    var se, Ce;
    let q = S;
    if (S === "class" && (q = ".%s"), S === "data" && (q = "[data-%s]"), S != null && S.startsWith("data-") && !S.includes("%s") && (q = `[${S}="%s"]`), de) {
      if (q === "media")
        return u.defaultColorScheme === de ? ":root" : {
          [`@media (prefers-color-scheme: ${((Ce = (se = T[de]) == null ? void 0 : se.palette) == null ? void 0 : Ce.mode) || de})`]: {
            ":root": ue
          }
        };
      if (q)
        return u.defaultColorScheme === de ? `:root, ${q.replace("%s", String(de))}` : q.replace("%s", String(de));
    }
    return ":root";
  }
  return {
    vars: U,
    generateThemeVars: () => {
      let de = {
        ...z
      };
      return Object.entries(te).forEach(([, {
        vars: ue
      }]) => {
        de = ki(de, ue);
      }), de;
    },
    generateStyleSheets: () => {
      var Ge, _t;
      const de = [], ue = u.defaultColorScheme || "light";
      function q(x, ge) {
        Object.keys(ge).length && de.push(typeof x == "string" ? {
          [x]: {
            ...ge
          }
        } : x);
      }
      q(v(void 0, {
        ...A
      }), A);
      const {
        [ue]: se,
        ...Ce
      } = te;
      if (se) {
        const {
          css: x
        } = se, ge = (_t = (Ge = T[ue]) == null ? void 0 : Ge.palette) == null ? void 0 : _t.mode, je = !y && ge ? {
          colorScheme: ge,
          ...x
        } : {
          ...x
        };
        q(v(ue, {
          ...je
        }), je);
      }
      return Object.entries(Ce).forEach(([x, {
        css: ge
      }]) => {
        var Pe, pt;
        const je = (pt = (Pe = T[x]) == null ? void 0 : Pe.palette) == null ? void 0 : pt.mode, Qe = !y && je ? {
          colorScheme: je,
          ...ge
        } : {
          ...ge
        };
        q(v(x, {
          ...Qe
        }), Qe);
      }), de;
    }
  };
}
var _L = {};
function kL(u) {
  return function(v) {
    return u === "media" ? (_L.NODE_ENV !== "production" && v !== "light" && v !== "dark" && console.error(`MUI: @media (prefers-color-scheme) supports only 'light' or 'dark', but receive '${v}'.`), `@media (prefers-color-scheme: ${v})`) : u ? u.startsWith("data-") && !u.includes("%s") ? `[${u}="${v}"] &` : u === "class" ? `.${v} &` : u === "data" ? `[data-${v}] &` : `${u.replace("%s", v)} &` : "&";
  };
}
const th = {
  black: "#000",
  white: "#fff"
}, OL = {
  50: "#fafafa",
  100: "#f5f5f5",
  200: "#eeeeee",
  300: "#e0e0e0",
  400: "#bdbdbd",
  500: "#9e9e9e",
  600: "#757575",
  700: "#616161",
  800: "#424242",
  900: "#212121",
  A100: "#f5f5f5",
  A200: "#eeeeee",
  A400: "#bdbdbd",
  A700: "#616161"
}, Dd = {
  50: "#f3e5f5",
  200: "#ce93d8",
  300: "#ba68c8",
  400: "#ab47bc",
  500: "#9c27b0",
  700: "#7b1fa2"
}, Nd = {
  300: "#e57373",
  400: "#ef5350",
  500: "#f44336",
  700: "#d32f2f",
  800: "#c62828"
}, Wv = {
  300: "#ffb74d",
  400: "#ffa726",
  500: "#ff9800",
  700: "#f57c00",
  900: "#e65100"
}, Ad = {
  50: "#e3f2fd",
  200: "#90caf9",
  400: "#42a5f5",
  700: "#1976d2",
  800: "#1565c0"
}, Md = {
  300: "#4fc3f7",
  400: "#29b6f6",
  500: "#03a9f4",
  700: "#0288d1",
  900: "#01579b"
}, Ld = {
  300: "#81c784",
  400: "#66bb6a",
  500: "#4caf50",
  700: "#388e3c",
  800: "#2e7d32",
  900: "#1b5e20"
};
var ng = {};
function Nw() {
  return {
    // The colors used to style the text.
    text: {
      // The most important text.
      primary: "rgba(0, 0, 0, 0.87)",
      // Secondary text.
      secondary: "rgba(0, 0, 0, 0.6)",
      // Disabled text have even lower visual prominence.
      disabled: "rgba(0, 0, 0, 0.38)"
    },
    // The color used to divide different elements.
    divider: "rgba(0, 0, 0, 0.12)",
    // The background colors used to style the surfaces.
    // Consistency between these values is important.
    background: {
      paper: th.white,
      default: th.white
    },
    // The colors used to style the action elements.
    action: {
      // The color of an active action like an icon button.
      active: "rgba(0, 0, 0, 0.54)",
      // The color of an hovered action.
      hover: "rgba(0, 0, 0, 0.04)",
      hoverOpacity: 0.04,
      // The color of a selected action.
      selected: "rgba(0, 0, 0, 0.08)",
      selectedOpacity: 0.08,
      // The color of a disabled action.
      disabled: "rgba(0, 0, 0, 0.26)",
      // The background color of a disabled action.
      disabledBackground: "rgba(0, 0, 0, 0.12)",
      disabledOpacity: 0.38,
      focus: "rgba(0, 0, 0, 0.12)",
      focusOpacity: 0.12,
      activatedOpacity: 0.12
    }
  };
}
const DL = Nw();
function Aw() {
  return {
    text: {
      primary: th.white,
      secondary: "rgba(255, 255, 255, 0.7)",
      disabled: "rgba(255, 255, 255, 0.5)",
      icon: "rgba(255, 255, 255, 0.5)"
    },
    divider: "rgba(255, 255, 255, 0.12)",
    background: {
      paper: "#121212",
      default: "#121212"
    },
    action: {
      active: th.white,
      hover: "rgba(255, 255, 255, 0.08)",
      hoverOpacity: 0.08,
      selected: "rgba(255, 255, 255, 0.16)",
      selectedOpacity: 0.16,
      disabled: "rgba(255, 255, 255, 0.3)",
      disabledBackground: "rgba(255, 255, 255, 0.12)",
      disabledOpacity: 0.38,
      focus: "rgba(255, 255, 255, 0.12)",
      focusOpacity: 0.12,
      activatedOpacity: 0.24
    }
  };
}
const QR = Aw();
function qR(u, f, v, y) {
  const S = y.light || y, T = y.dark || y * 1.5;
  u[f] || (u.hasOwnProperty(v) ? u[f] = u[v] : f === "light" ? u.light = RC(u.main, S) : f === "dark" && (u.dark = TC(u.main, T)));
}
function NL(u = "light") {
  return u === "dark" ? {
    main: Ad[200],
    light: Ad[50],
    dark: Ad[400]
  } : {
    main: Ad[700],
    light: Ad[400],
    dark: Ad[800]
  };
}
function AL(u = "light") {
  return u === "dark" ? {
    main: Dd[200],
    light: Dd[50],
    dark: Dd[400]
  } : {
    main: Dd[500],
    light: Dd[300],
    dark: Dd[700]
  };
}
function ML(u = "light") {
  return u === "dark" ? {
    main: Nd[500],
    light: Nd[300],
    dark: Nd[700]
  } : {
    main: Nd[700],
    light: Nd[400],
    dark: Nd[800]
  };
}
function LL(u = "light") {
  return u === "dark" ? {
    main: Md[400],
    light: Md[300],
    dark: Md[700]
  } : {
    main: Md[700],
    light: Md[500],
    dark: Md[900]
  };
}
function zL(u = "light") {
  return u === "dark" ? {
    main: Ld[400],
    light: Ld[300],
    dark: Ld[700]
  } : {
    main: Ld[800],
    light: Ld[500],
    dark: Ld[900]
  };
}
function UL(u = "light") {
  return u === "dark" ? {
    main: Wv[400],
    light: Wv[300],
    dark: Wv[700]
  } : {
    main: "#ed6c02",
    // closest to orange[800] that pass 3:1.
    light: Wv[500],
    dark: Wv[900]
  };
}
function wC(u) {
  const {
    mode: f = "light",
    contrastThreshold: v = 3,
    tonalOffset: y = 0.2,
    ...S
  } = u, T = u.primary || NL(f), _ = u.secondary || AL(f), g = u.error || ML(f), L = u.info || LL(f), z = u.success || zL(f), A = u.warning || UL(f);
  function F(M) {
    const j = YR(M, QR.text.primary) >= v ? QR.text.primary : DL.text.primary;
    if (ng.NODE_ENV !== "production") {
      const ce = YR(M, j);
      ce < 3 && console.error([`MUI: The contrast ratio of ${ce}:1 for ${j} on ${M}`, "falls below the WCAG recommended absolute minimum contrast ratio of 3:1.", "https://www.w3.org/TR/2008/REC-WCAG20-20081211/#visual-audio-contrast-contrast"].join(`
`));
    }
    return j;
  }
  const U = ({
    color: M,
    name: j,
    mainShade: ce = 500,
    lightShade: De = 300,
    darkShade: de = 700
  }) => {
    if (M = {
      ...M
    }, !M.main && M[ce] && (M.main = M[ce]), !M.hasOwnProperty("main"))
      throw new Error(ng.NODE_ENV !== "production" ? `MUI: The color${j ? ` (${j})` : ""} provided to augmentColor(color) is invalid.
The color object needs to have a \`main\` property or a \`${ce}\` property.` : gs(11, j ? ` (${j})` : "", ce));
    if (typeof M.main != "string")
      throw new Error(ng.NODE_ENV !== "production" ? `MUI: The color${j ? ` (${j})` : ""} provided to augmentColor(color) is invalid.
\`color.main\` should be a string, but \`${JSON.stringify(M.main)}\` was provided instead.

Did you intend to use one of the following approaches?

import { green } from "@mui/material/colors";

const theme1 = createTheme({ palette: {
  primary: green,
} });

const theme2 = createTheme({ palette: {
  primary: { main: green[500] },
} });` : gs(12, j ? ` (${j})` : "", JSON.stringify(M.main)));
    return qR(M, "light", De, y), qR(M, "dark", de, y), M.contrastText || (M.contrastText = F(M.main)), M;
  };
  let te;
  return f === "light" ? te = Nw() : f === "dark" && (te = Aw()), ng.NODE_ENV !== "production" && (te || console.error(`MUI: The palette mode \`${f}\` is not supported.`)), ki({
    // A collection of common colors.
    common: {
      ...th
    },
    // prevent mutable object.
    // The palette mode, can be light or dark.
    mode: f,
    // The colors used to represent primary interface elements for a user.
    primary: U({
      color: T,
      name: "primary"
    }),
    // The colors used to represent secondary interface elements for a user.
    secondary: U({
      color: _,
      name: "secondary",
      mainShade: "A400",
      lightShade: "A200",
      darkShade: "A700"
    }),
    // The colors used to represent interface elements that the user should be made aware of.
    error: U({
      color: g,
      name: "error"
    }),
    // The colors used to represent potentially dangerous actions or important messages.
    warning: U({
      color: A,
      name: "warning"
    }),
    // The colors used to present information to the user that is neutral and not necessarily important.
    info: U({
      color: L,
      name: "info"
    }),
    // The colors used to indicate the successful completion of an action that user triggered.
    success: U({
      color: z,
      name: "success"
    }),
    // The grey colors.
    grey: OL,
    // Used by `getContrastText()` to maximize the contrast between
    // the background and the text.
    contrastThreshold: v,
    // Takes a background color and returns the text color that maximizes the contrast.
    getContrastText: F,
    // Generate a rich color object.
    augmentColor: U,
    // Used by the functions below to shift a color's luminance by approximately
    // two indexes within its tonal palette.
    // E.g., shift from Red 500 to Red 300 or Red 700.
    tonalOffset: y,
    // The light and dark mode object.
    ...te
  }, S);
}
function PL(u) {
  const f = {};
  return Object.entries(u).forEach((y) => {
    const [S, T] = y;
    typeof T == "object" && (f[S] = `${T.fontStyle ? `${T.fontStyle} ` : ""}${T.fontVariant ? `${T.fontVariant} ` : ""}${T.fontWeight ? `${T.fontWeight} ` : ""}${T.fontStretch ? `${T.fontStretch} ` : ""}${T.fontSize || ""}${T.lineHeight ? `/${T.lineHeight} ` : ""}${T.fontFamily || ""}`);
  }), f;
}
function $L(u, f) {
  return {
    toolbar: {
      minHeight: 56,
      [u.up("xs")]: {
        "@media (orientation: landscape)": {
          minHeight: 48
        }
      },
      [u.up("sm")]: {
        minHeight: 64
      }
    },
    ...f
  };
}
var FL = {};
function jL(u) {
  return Math.round(u * 1e5) / 1e5;
}
const KR = {
  textTransform: "uppercase"
}, XR = '"Roboto", "Helvetica", "Arial", sans-serif';
function HL(u, f) {
  const {
    fontFamily: v = XR,
    // The default font size of the Material Specification.
    fontSize: y = 14,
    // px
    fontWeightLight: S = 300,
    fontWeightRegular: T = 400,
    fontWeightMedium: _ = 500,
    fontWeightBold: g = 700,
    // Tell MUI what's the font-size on the html element.
    // 16px is the default font-size used by browsers.
    htmlFontSize: L = 16,
    // Apply the CSS properties to all the variants.
    allVariants: z,
    pxToRem: A,
    ...F
  } = typeof f == "function" ? f(u) : f;
  FL.NODE_ENV !== "production" && (typeof y != "number" && console.error("MUI: `fontSize` is required to be a number."), typeof L != "number" && console.error("MUI: `htmlFontSize` is required to be a number."));
  const U = y / 14, te = A || ((j) => `${j / L * U}rem`), B = (j, ce, De, de, ue) => ({
    fontFamily: v,
    fontWeight: j,
    fontSize: te(ce),
    // Unitless following https://meyerweb.com/eric/thoughts/2006/02/08/unitless-line-heights/
    lineHeight: De,
    // The letter spacing was designed for the Roboto font-family. Using the same letter-spacing
    // across font-families can cause issues with the kerning.
    ...v === XR ? {
      letterSpacing: `${jL(de / ce)}em`
    } : {},
    ...ue,
    ...z
  }), M = {
    h1: B(S, 96, 1.167, -1.5),
    h2: B(S, 60, 1.2, -0.5),
    h3: B(T, 48, 1.167, 0),
    h4: B(T, 34, 1.235, 0.25),
    h5: B(T, 24, 1.334, 0),
    h6: B(_, 20, 1.6, 0.15),
    subtitle1: B(T, 16, 1.75, 0.15),
    subtitle2: B(_, 14, 1.57, 0.1),
    body1: B(T, 16, 1.5, 0.15),
    body2: B(T, 14, 1.43, 0.15),
    button: B(_, 14, 1.75, 0.4, KR),
    caption: B(T, 12, 1.66, 0.4),
    overline: B(T, 12, 2.66, 1, KR),
    // TODO v6: Remove handling of 'inherit' variant from the theme as it is already handled in Material UI's Typography component. Also, remember to remove the associated types.
    inherit: {
      fontFamily: "inherit",
      fontWeight: "inherit",
      fontSize: "inherit",
      lineHeight: "inherit",
      letterSpacing: "inherit"
    }
  };
  return ki({
    htmlFontSize: L,
    pxToRem: te,
    fontFamily: v,
    fontSize: y,
    fontWeightLight: S,
    fontWeightRegular: T,
    fontWeightMedium: _,
    fontWeightBold: g,
    ...M
  }, F, {
    clone: !1
    // No need to clone deep
  });
}
const VL = 0.2, BL = 0.14, IL = 0.12;
function $n(...u) {
  return [`${u[0]}px ${u[1]}px ${u[2]}px ${u[3]}px rgba(0,0,0,${VL})`, `${u[4]}px ${u[5]}px ${u[6]}px ${u[7]}px rgba(0,0,0,${BL})`, `${u[8]}px ${u[9]}px ${u[10]}px ${u[11]}px rgba(0,0,0,${IL})`].join(",");
}
const YL = ["none", $n(0, 2, 1, -1, 0, 1, 1, 0, 0, 1, 3, 0), $n(0, 3, 1, -2, 0, 2, 2, 0, 0, 1, 5, 0), $n(0, 3, 3, -2, 0, 3, 4, 0, 0, 1, 8, 0), $n(0, 2, 4, -1, 0, 4, 5, 0, 0, 1, 10, 0), $n(0, 3, 5, -1, 0, 5, 8, 0, 0, 1, 14, 0), $n(0, 3, 5, -1, 0, 6, 10, 0, 0, 1, 18, 0), $n(0, 4, 5, -2, 0, 7, 10, 1, 0, 2, 16, 1), $n(0, 5, 5, -3, 0, 8, 10, 1, 0, 3, 14, 2), $n(0, 5, 6, -3, 0, 9, 12, 1, 0, 3, 16, 2), $n(0, 6, 6, -3, 0, 10, 14, 1, 0, 4, 18, 3), $n(0, 6, 7, -4, 0, 11, 15, 1, 0, 4, 20, 3), $n(0, 7, 8, -4, 0, 12, 17, 2, 0, 5, 22, 4), $n(0, 7, 8, -4, 0, 13, 19, 2, 0, 5, 24, 4), $n(0, 7, 9, -4, 0, 14, 21, 2, 0, 5, 26, 4), $n(0, 8, 9, -5, 0, 15, 22, 2, 0, 6, 28, 5), $n(0, 8, 10, -5, 0, 16, 24, 2, 0, 6, 30, 5), $n(0, 8, 11, -5, 0, 17, 26, 2, 0, 6, 32, 5), $n(0, 9, 11, -5, 0, 18, 28, 2, 0, 7, 34, 6), $n(0, 9, 12, -6, 0, 19, 29, 2, 0, 7, 36, 6), $n(0, 10, 13, -6, 0, 20, 31, 3, 0, 8, 38, 7), $n(0, 10, 13, -6, 0, 21, 33, 3, 0, 8, 40, 7), $n(0, 10, 14, -6, 0, 22, 35, 3, 0, 8, 42, 7), $n(0, 11, 14, -7, 0, 23, 36, 3, 0, 9, 44, 8), $n(0, 11, 15, -7, 0, 24, 38, 3, 0, 9, 46, 8)];
var WL = {};
const GL = {
  // This is the most common easing curve.
  easeInOut: "cubic-bezier(0.4, 0, 0.2, 1)",
  // Objects enter the screen at full velocity from off-screen and
  // slowly decelerate to a resting point.
  easeOut: "cubic-bezier(0.0, 0, 0.2, 1)",
  // Objects leave the screen at full velocity. They do not decelerate when off-screen.
  easeIn: "cubic-bezier(0.4, 0, 1, 1)",
  // The sharp curve is used by objects that may return to the screen at any time.
  sharp: "cubic-bezier(0.4, 0, 0.6, 1)"
}, QL = {
  shortest: 150,
  shorter: 200,
  short: 250,
  // most basic recommended timing
  standard: 300,
  // this is to be used in complex animations
  complex: 375,
  // recommended when something is entering screen
  enteringScreen: 225,
  // recommended when something is leaving screen
  leavingScreen: 195
};
function JR(u) {
  return `${Math.round(u)}ms`;
}
function qL(u) {
  if (!u)
    return 0;
  const f = u / 36;
  return Math.min(Math.round((4 + 15 * f ** 0.25 + f / 5) * 10), 3e3);
}
function KL(u) {
  const f = {
    ...GL,
    ...u.easing
  }, v = {
    ...QL,
    ...u.duration
  };
  return {
    getAutoHeightDuration: qL,
    create: (S = ["all"], T = {}) => {
      const {
        duration: _ = v.standard,
        easing: g = f.easeInOut,
        delay: L = 0,
        ...z
      } = T;
      if (WL.NODE_ENV !== "production") {
        const A = (U) => typeof U == "string", F = (U) => !Number.isNaN(parseFloat(U));
        !A(S) && !Array.isArray(S) && console.error('MUI: Argument "props" must be a string or Array.'), !F(_) && !A(_) && console.error(`MUI: Argument "duration" must be a number or a string but found ${_}.`), A(g) || console.error('MUI: Argument "easing" must be a string.'), !F(L) && !A(L) && console.error('MUI: Argument "delay" must be a number or a string.'), typeof T != "object" && console.error(["MUI: Secong argument of transition.create must be an object.", "Arguments should be either `create('prop1', options)` or `create(['prop1', 'prop2'], options)`"].join(`
`)), Object.keys(z).length !== 0 && console.error(`MUI: Unrecognized argument(s) [${Object.keys(z).join(",")}].`);
      }
      return (Array.isArray(S) ? S : [S]).map((A) => `${A} ${typeof _ == "string" ? _ : JR(_)} ${g} ${typeof L == "string" ? L : JR(L)}`).join(",");
    },
    ...u,
    easing: f,
    duration: v
  };
}
const XL = {
  mobileStepper: 1e3,
  fab: 1050,
  speedDial: 1050,
  appBar: 1100,
  drawer: 1200,
  modal: 1300,
  snackbar: 1400,
  tooltip: 1500
};
function JL(u) {
  return pu(u) || typeof u > "u" || typeof u == "string" || typeof u == "boolean" || typeof u == "number" || Array.isArray(u);
}
function Mw(u = {}) {
  const f = {
    ...u
  };
  function v(y) {
    const S = Object.entries(y);
    for (let T = 0; T < S.length; T++) {
      const [_, g] = S[T];
      !JL(g) || _.startsWith("unstable_") ? delete y[_] : pu(g) && (y[_] = {
        ...g
      }, v(y[_]));
    }
  }
  return v(f), `import { unstable_createBreakpoints as createBreakpoints, createTransitions } from '@mui/material/styles';

const theme = ${JSON.stringify(f, null, 2)};

theme.breakpoints = createBreakpoints(theme.breakpoints || {});
theme.transitions = createTransitions(theme.transitions || {});

export default theme;`;
}
var ZE = {};
function pC(u = {}, ...f) {
  const {
    breakpoints: v,
    mixins: y = {},
    spacing: S,
    palette: T = {},
    transitions: _ = {},
    typography: g = {},
    shape: L,
    ...z
  } = u;
  if (u.vars && // The error should throw only for the root theme creation because user is not allowed to use a custom node `vars`.
  // `generateThemeVars` is the closest identifier for checking that the `options` is a result of `createTheme` with CSS variables so that user can create new theme for nested ThemeProvider.
  u.generateThemeVars === void 0)
    throw new Error(ZE.NODE_ENV !== "production" ? "MUI: `vars` is a private field used for CSS variables support.\nPlease use another name or follow the [docs](https://mui.com/material-ui/customization/css-theme-variables/usage/) to enable the feature." : gs(20));
  const A = wC(T), F = ww(u);
  let U = ki(F, {
    mixins: $L(F.breakpoints, y),
    palette: A,
    // Don't use [...shadows] until you've verified its transpiled code is not invoking the iterator protocol.
    shadows: YL.slice(),
    typography: HL(A, g),
    transitions: KL(_),
    zIndex: {
      ...XL
    }
  });
  if (U = ki(U, z), U = f.reduce((te, B) => ki(te, B), U), ZE.NODE_ENV !== "production") {
    const te = ["active", "checked", "completed", "disabled", "error", "expanded", "focused", "focusVisible", "required", "selected"], B = (M, j) => {
      let ce;
      for (ce in M) {
        const De = M[ce];
        if (te.includes(ce) && Object.keys(De).length > 0) {
          if (ZE.NODE_ENV !== "production") {
            const de = hC("", ce);
            console.error([`MUI: The \`${j}\` component increases the CSS specificity of the \`${ce}\` internal state.`, "You can not override it like this: ", JSON.stringify(M, null, 2), "", `Instead, you need to use the '&.${de}' syntax:`, JSON.stringify({
              root: {
                [`&.${de}`]: De
              }
            }, null, 2), "", "https://mui.com/r/state-classes-guide"].join(`
`));
          }
          M[ce] = {};
        }
      }
    };
    Object.keys(U.components).forEach((M) => {
      const j = U.components[M].styleOverrides;
      j && M.startsWith("Mui") && B(j, M);
    });
  }
  return U.unstable_sxConfig = {
    ...Eg,
    ...z == null ? void 0 : z.unstable_sxConfig
  }, U.unstable_sx = function(B) {
    return $d({
      sx: B,
      theme: this
    });
  }, U.toRuntimeSource = Mw, U;
}
function ZL(u) {
  let f;
  return u < 1 ? f = 5.11916 * u ** 2 : f = 4.5 * Math.log(u + 1) + 2, Math.round(f * 10) / 1e3;
}
const ez = [...Array(25)].map((u, f) => {
  if (f === 0)
    return "none";
  const v = ZL(f);
  return `linear-gradient(rgba(255 255 255 / ${v}), rgba(255 255 255 / ${v}))`;
});
function Lw(u) {
  return {
    inputPlaceholder: u === "dark" ? 0.5 : 0.42,
    inputUnderline: u === "dark" ? 0.7 : 0.42,
    switchTrackDisabled: u === "dark" ? 0.2 : 0.12,
    switchTrack: u === "dark" ? 0.3 : 0.38
  };
}
function zw(u) {
  return u === "dark" ? ez : [];
}
function tz(u) {
  const {
    palette: f = {
      mode: "light"
    },
    // need to cast to avoid module augmentation test
    opacity: v,
    overlays: y,
    ...S
  } = u, T = wC(f);
  return {
    palette: T,
    opacity: {
      ...Lw(T.mode),
      ...v
    },
    overlays: y || zw(T.mode),
    ...S
  };
}
function nz(u) {
  var f;
  return !!u[0].match(/(cssVarPrefix|colorSchemeSelector|rootSelector|typography|mixins|breakpoints|direction|transitions)/) || !!u[0].match(/sxConfig$/) || // ends with sxConfig
  u[0] === "palette" && !!((f = u[1]) != null && f.match(/(mode|contrastThreshold|tonalOffset)/));
}
const rz = (u) => [...[...Array(25)].map((f, v) => `--${u ? `${u}-` : ""}overlays-${v}`), `--${u ? `${u}-` : ""}palette-AppBar-darkBg`, `--${u ? `${u}-` : ""}palette-AppBar-darkColor`], az = (u) => (f, v) => {
  const y = u.rootSelector || ":root", S = u.colorSchemeSelector;
  let T = S;
  if (S === "class" && (T = ".%s"), S === "data" && (T = "[data-%s]"), S != null && S.startsWith("data-") && !S.includes("%s") && (T = `[${S}="%s"]`), u.defaultColorScheme === f) {
    if (f === "dark") {
      const _ = {};
      return rz(u.cssVarPrefix).forEach((g) => {
        _[g] = v[g], delete v[g];
      }), T === "media" ? {
        [y]: v,
        "@media (prefers-color-scheme: dark)": {
          [y]: _
        }
      } : T ? {
        [T.replace("%s", f)]: _,
        [`${y}, ${T.replace("%s", f)}`]: v
      } : {
        [y]: {
          ...v,
          ..._
        }
      };
    }
    if (T && T !== "media")
      return `${y}, ${T.replace("%s", String(f))}`;
  } else if (f) {
    if (T === "media")
      return {
        [`@media (prefers-color-scheme: ${String(f)})`]: {
          [y]: v
        }
      };
    if (T)
      return T.replace("%s", String(f));
  }
  return y;
};
var iz = {};
function oz(u, f) {
  f.forEach((v) => {
    u[v] || (u[v] = {});
  });
}
function ae(u, f, v) {
  !u[f] && v && (u[f] = v);
}
function qv(u) {
  return typeof u != "string" || !u.startsWith("hsl") ? u : Dw(u);
}
function du(u, f) {
  `${f}Channel` in u || (u[`${f}Channel`] = Qv(qv(u[f]), `MUI: Can't create \`palette.${f}Channel\` because \`palette.${f}\` is not one of these formats: #nnn, #nnnnnn, rgb(), rgba(), hsl(), hsla(), color().
To suppress this warning, you need to explicitly provide the \`palette.${f}Channel\` as a string (in rgb format, for example "12 12 12") or undefined if you want to remove the channel token.`));
}
function lz(u) {
  return typeof u == "number" ? `${u}px` : typeof u == "string" || typeof u == "function" || Array.isArray(u) ? u : "8px";
}
const hl = (u) => {
  try {
    return u();
  } catch {
  }
}, uz = (u = "mui") => TL(u);
function eC(u, f, v, y) {
  if (!f)
    return;
  f = f === !0 ? {} : f;
  const S = y === "dark" ? "dark" : "light";
  if (!v) {
    u[y] = tz({
      ...f,
      palette: {
        mode: S,
        ...f == null ? void 0 : f.palette
      }
    });
    return;
  }
  const {
    palette: T,
    ..._
  } = pC({
    ...v,
    palette: {
      mode: S,
      ...f == null ? void 0 : f.palette
    }
  });
  return u[y] = {
    ...f,
    palette: T,
    opacity: {
      ...Lw(S),
      ...f == null ? void 0 : f.opacity
    },
    overlays: (f == null ? void 0 : f.overlays) || zw(S)
  }, _;
}
function sz(u = {}, ...f) {
  const {
    colorSchemes: v = {
      light: !0
    },
    defaultColorScheme: y,
    disableCssColorScheme: S = !1,
    cssVarPrefix: T = "mui",
    shouldSkipGeneratingVar: _ = nz,
    colorSchemeSelector: g = v.light && v.dark ? "media" : void 0,
    rootSelector: L = ":root",
    ...z
  } = u, A = Object.keys(v)[0], F = y || (v.light && A !== "light" ? "light" : A), U = uz(T), {
    [F]: te,
    light: B,
    dark: M,
    ...j
  } = v, ce = {
    ...j
  };
  let De = te;
  if ((F === "dark" && !("dark" in v) || F === "light" && !("light" in v)) && (De = !0), !De)
    throw new Error(iz.NODE_ENV !== "production" ? `MUI: The \`colorSchemes.${F}\` option is either missing or invalid.` : gs(21, F));
  const de = eC(ce, De, z, F);
  B && !ce.light && eC(ce, B, void 0, "light"), M && !ce.dark && eC(ce, M, void 0, "dark");
  let ue = {
    defaultColorScheme: F,
    ...de,
    cssVarPrefix: T,
    colorSchemeSelector: g,
    rootSelector: L,
    getCssVar: U,
    colorSchemes: ce,
    font: {
      ...PL(de.typography),
      ...de.font
    },
    spacing: lz(z.spacing)
  };
  Object.keys(ue.colorSchemes).forEach((_t) => {
    const x = ue.colorSchemes[_t].palette, ge = (je) => {
      const Qe = je.split("-"), Pe = Qe[1], pt = Qe[2];
      return U(je, x[Pe][pt]);
    };
    if (x.mode === "light" && (ae(x.common, "background", "#fff"), ae(x.common, "onBackground", "#000")), x.mode === "dark" && (ae(x.common, "background", "#000"), ae(x.common, "onBackground", "#fff")), oz(x, ["Alert", "AppBar", "Avatar", "Button", "Chip", "FilledInput", "LinearProgress", "Skeleton", "Slider", "SnackbarContent", "SpeedDialAction", "StepConnector", "StepContent", "Switch", "TableCell", "Tooltip"]), x.mode === "light") {
      ae(x.Alert, "errorColor", kn(x.error.light, 0.6)), ae(x.Alert, "infoColor", kn(x.info.light, 0.6)), ae(x.Alert, "successColor", kn(x.success.light, 0.6)), ae(x.Alert, "warningColor", kn(x.warning.light, 0.6)), ae(x.Alert, "errorFilledBg", ge("palette-error-main")), ae(x.Alert, "infoFilledBg", ge("palette-info-main")), ae(x.Alert, "successFilledBg", ge("palette-success-main")), ae(x.Alert, "warningFilledBg", ge("palette-warning-main")), ae(x.Alert, "errorFilledColor", hl(() => x.getContrastText(x.error.main))), ae(x.Alert, "infoFilledColor", hl(() => x.getContrastText(x.info.main))), ae(x.Alert, "successFilledColor", hl(() => x.getContrastText(x.success.main))), ae(x.Alert, "warningFilledColor", hl(() => x.getContrastText(x.warning.main))), ae(x.Alert, "errorStandardBg", On(x.error.light, 0.9)), ae(x.Alert, "infoStandardBg", On(x.info.light, 0.9)), ae(x.Alert, "successStandardBg", On(x.success.light, 0.9)), ae(x.Alert, "warningStandardBg", On(x.warning.light, 0.9)), ae(x.Alert, "errorIconColor", ge("palette-error-main")), ae(x.Alert, "infoIconColor", ge("palette-info-main")), ae(x.Alert, "successIconColor", ge("palette-success-main")), ae(x.Alert, "warningIconColor", ge("palette-warning-main")), ae(x.AppBar, "defaultBg", ge("palette-grey-100")), ae(x.Avatar, "defaultBg", ge("palette-grey-400")), ae(x.Button, "inheritContainedBg", ge("palette-grey-300")), ae(x.Button, "inheritContainedHoverBg", ge("palette-grey-A100")), ae(x.Chip, "defaultBorder", ge("palette-grey-400")), ae(x.Chip, "defaultAvatarColor", ge("palette-grey-700")), ae(x.Chip, "defaultIconColor", ge("palette-grey-700")), ae(x.FilledInput, "bg", "rgba(0, 0, 0, 0.06)"), ae(x.FilledInput, "hoverBg", "rgba(0, 0, 0, 0.09)"), ae(x.FilledInput, "disabledBg", "rgba(0, 0, 0, 0.12)"), ae(x.LinearProgress, "primaryBg", On(x.primary.main, 0.62)), ae(x.LinearProgress, "secondaryBg", On(x.secondary.main, 0.62)), ae(x.LinearProgress, "errorBg", On(x.error.main, 0.62)), ae(x.LinearProgress, "infoBg", On(x.info.main, 0.62)), ae(x.LinearProgress, "successBg", On(x.success.main, 0.62)), ae(x.LinearProgress, "warningBg", On(x.warning.main, 0.62)), ae(x.Skeleton, "bg", `rgba(${ge("palette-text-primaryChannel")} / 0.11)`), ae(x.Slider, "primaryTrack", On(x.primary.main, 0.62)), ae(x.Slider, "secondaryTrack", On(x.secondary.main, 0.62)), ae(x.Slider, "errorTrack", On(x.error.main, 0.62)), ae(x.Slider, "infoTrack", On(x.info.main, 0.62)), ae(x.Slider, "successTrack", On(x.success.main, 0.62)), ae(x.Slider, "warningTrack", On(x.warning.main, 0.62));
      const je = tg(x.background.default, 0.8);
      ae(x.SnackbarContent, "bg", je), ae(x.SnackbarContent, "color", hl(() => x.getContrastText(je))), ae(x.SpeedDialAction, "fabHoverBg", tg(x.background.paper, 0.15)), ae(x.StepConnector, "border", ge("palette-grey-400")), ae(x.StepContent, "border", ge("palette-grey-400")), ae(x.Switch, "defaultColor", ge("palette-common-white")), ae(x.Switch, "defaultDisabledColor", ge("palette-grey-100")), ae(x.Switch, "primaryDisabledColor", On(x.primary.main, 0.62)), ae(x.Switch, "secondaryDisabledColor", On(x.secondary.main, 0.62)), ae(x.Switch, "errorDisabledColor", On(x.error.main, 0.62)), ae(x.Switch, "infoDisabledColor", On(x.info.main, 0.62)), ae(x.Switch, "successDisabledColor", On(x.success.main, 0.62)), ae(x.Switch, "warningDisabledColor", On(x.warning.main, 0.62)), ae(x.TableCell, "border", On(eg(x.divider, 1), 0.88)), ae(x.Tooltip, "bg", eg(x.grey[700], 0.92));
    }
    if (x.mode === "dark") {
      ae(x.Alert, "errorColor", On(x.error.light, 0.6)), ae(x.Alert, "infoColor", On(x.info.light, 0.6)), ae(x.Alert, "successColor", On(x.success.light, 0.6)), ae(x.Alert, "warningColor", On(x.warning.light, 0.6)), ae(x.Alert, "errorFilledBg", ge("palette-error-dark")), ae(x.Alert, "infoFilledBg", ge("palette-info-dark")), ae(x.Alert, "successFilledBg", ge("palette-success-dark")), ae(x.Alert, "warningFilledBg", ge("palette-warning-dark")), ae(x.Alert, "errorFilledColor", hl(() => x.getContrastText(x.error.dark))), ae(x.Alert, "infoFilledColor", hl(() => x.getContrastText(x.info.dark))), ae(x.Alert, "successFilledColor", hl(() => x.getContrastText(x.success.dark))), ae(x.Alert, "warningFilledColor", hl(() => x.getContrastText(x.warning.dark))), ae(x.Alert, "errorStandardBg", kn(x.error.light, 0.9)), ae(x.Alert, "infoStandardBg", kn(x.info.light, 0.9)), ae(x.Alert, "successStandardBg", kn(x.success.light, 0.9)), ae(x.Alert, "warningStandardBg", kn(x.warning.light, 0.9)), ae(x.Alert, "errorIconColor", ge("palette-error-main")), ae(x.Alert, "infoIconColor", ge("palette-info-main")), ae(x.Alert, "successIconColor", ge("palette-success-main")), ae(x.Alert, "warningIconColor", ge("palette-warning-main")), ae(x.AppBar, "defaultBg", ge("palette-grey-900")), ae(x.AppBar, "darkBg", ge("palette-background-paper")), ae(x.AppBar, "darkColor", ge("palette-text-primary")), ae(x.Avatar, "defaultBg", ge("palette-grey-600")), ae(x.Button, "inheritContainedBg", ge("palette-grey-800")), ae(x.Button, "inheritContainedHoverBg", ge("palette-grey-700")), ae(x.Chip, "defaultBorder", ge("palette-grey-700")), ae(x.Chip, "defaultAvatarColor", ge("palette-grey-300")), ae(x.Chip, "defaultIconColor", ge("palette-grey-300")), ae(x.FilledInput, "bg", "rgba(255, 255, 255, 0.09)"), ae(x.FilledInput, "hoverBg", "rgba(255, 255, 255, 0.13)"), ae(x.FilledInput, "disabledBg", "rgba(255, 255, 255, 0.12)"), ae(x.LinearProgress, "primaryBg", kn(x.primary.main, 0.5)), ae(x.LinearProgress, "secondaryBg", kn(x.secondary.main, 0.5)), ae(x.LinearProgress, "errorBg", kn(x.error.main, 0.5)), ae(x.LinearProgress, "infoBg", kn(x.info.main, 0.5)), ae(x.LinearProgress, "successBg", kn(x.success.main, 0.5)), ae(x.LinearProgress, "warningBg", kn(x.warning.main, 0.5)), ae(x.Skeleton, "bg", `rgba(${ge("palette-text-primaryChannel")} / 0.13)`), ae(x.Slider, "primaryTrack", kn(x.primary.main, 0.5)), ae(x.Slider, "secondaryTrack", kn(x.secondary.main, 0.5)), ae(x.Slider, "errorTrack", kn(x.error.main, 0.5)), ae(x.Slider, "infoTrack", kn(x.info.main, 0.5)), ae(x.Slider, "successTrack", kn(x.success.main, 0.5)), ae(x.Slider, "warningTrack", kn(x.warning.main, 0.5));
      const je = tg(x.background.default, 0.98);
      ae(x.SnackbarContent, "bg", je), ae(x.SnackbarContent, "color", hl(() => x.getContrastText(je))), ae(x.SpeedDialAction, "fabHoverBg", tg(x.background.paper, 0.15)), ae(x.StepConnector, "border", ge("palette-grey-600")), ae(x.StepContent, "border", ge("palette-grey-600")), ae(x.Switch, "defaultColor", ge("palette-grey-300")), ae(x.Switch, "defaultDisabledColor", ge("palette-grey-600")), ae(x.Switch, "primaryDisabledColor", kn(x.primary.main, 0.55)), ae(x.Switch, "secondaryDisabledColor", kn(x.secondary.main, 0.55)), ae(x.Switch, "errorDisabledColor", kn(x.error.main, 0.55)), ae(x.Switch, "infoDisabledColor", kn(x.info.main, 0.55)), ae(x.Switch, "successDisabledColor", kn(x.success.main, 0.55)), ae(x.Switch, "warningDisabledColor", kn(x.warning.main, 0.55)), ae(x.TableCell, "border", kn(eg(x.divider, 1), 0.68)), ae(x.Tooltip, "bg", eg(x.grey[700], 0.92));
    }
    du(x.background, "default"), du(x.background, "paper"), du(x.common, "background"), du(x.common, "onBackground"), du(x, "divider"), Object.keys(x).forEach((je) => {
      const Qe = x[je];
      je !== "tonalOffset" && Qe && typeof Qe == "object" && (Qe.main && ae(x[je], "mainChannel", Qv(qv(Qe.main))), Qe.light && ae(x[je], "lightChannel", Qv(qv(Qe.light))), Qe.dark && ae(x[je], "darkChannel", Qv(qv(Qe.dark))), Qe.contrastText && ae(x[je], "contrastTextChannel", Qv(qv(Qe.contrastText))), je === "text" && (du(x[je], "primary"), du(x[je], "secondary")), je === "action" && (Qe.active && du(x[je], "active"), Qe.selected && du(x[je], "selected")));
    });
  }), ue = f.reduce((_t, x) => ki(_t, x), ue);
  const q = {
    prefix: T,
    disableCssColorScheme: S,
    shouldSkipGeneratingVar: _,
    getSelector: az(ue)
  }, {
    vars: se,
    generateThemeVars: Ce,
    generateStyleSheets: Ge
  } = xL(ue, q);
  return ue.vars = se, Object.entries(ue.colorSchemes[ue.defaultColorScheme]).forEach(([_t, x]) => {
    ue[_t] = x;
  }), ue.generateThemeVars = Ce, ue.generateStyleSheets = Ge, ue.generateSpacing = function() {
    return Rw(z.spacing, mC(this));
  }, ue.getColorSchemeSelector = kL(g), ue.spacing = ue.generateSpacing(), ue.shouldSkipGeneratingVar = _, ue.unstable_sxConfig = {
    ...Eg,
    ...z == null ? void 0 : z.unstable_sxConfig
  }, ue.unstable_sx = function(x) {
    return $d({
      sx: x,
      theme: this
    });
  }, ue.toRuntimeSource = Mw, ue;
}
function ZR(u, f, v) {
  u.colorSchemes && v && (u.colorSchemes[f] = {
    ...v !== !0 && v,
    palette: wC({
      ...v === !0 ? {} : v.palette,
      mode: f
    })
    // cast type to skip module augmentation test
  });
}
function cz(u = {}, ...f) {
  const {
    palette: v,
    cssVariables: y = !1,
    colorSchemes: S = v ? void 0 : {
      light: !0
    },
    defaultColorScheme: T = v == null ? void 0 : v.mode,
    ..._
  } = u, g = T || "light", L = S == null ? void 0 : S[g], z = {
    ...S,
    ...v ? {
      [g]: {
        ...typeof L != "boolean" && L,
        palette: v
      }
    } : void 0
  };
  if (y === !1) {
    if (!("colorSchemes" in u))
      return pC(u, ...f);
    let A = v;
    "palette" in u || z[g] && (z[g] !== !0 ? A = z[g].palette : g === "dark" && (A = {
      mode: "dark"
    }));
    const F = pC({
      ...u,
      palette: A
    }, ...f);
    return F.defaultColorScheme = g, F.colorSchemes = z, F.palette.mode === "light" && (F.colorSchemes.light = {
      ...z.light !== !0 && z.light,
      palette: F.palette
    }, ZR(F, "dark", z.dark)), F.palette.mode === "dark" && (F.colorSchemes.dark = {
      ...z.dark !== !0 && z.dark,
      palette: F.palette
    }, ZR(F, "light", z.light)), F;
  }
  return !v && !("light" in z) && g === "light" && (z.light = !0), sz({
    ..._,
    colorSchemes: z,
    defaultColorScheme: g,
    ...typeof y != "boolean" && y
  }, ...f);
}
const fz = cz(), dz = "$$material";
function pz(u) {
  return u !== "ownerState" && u !== "theme" && u !== "sx" && u !== "as";
}
const vz = (u) => pz(u) && u !== "classes", hz = sL({
  themeId: dz,
  defaultTheme: fz,
  rootShouldForwardProp: vz
}), mz = bL;
var yz = {};
yz.NODE_ENV !== "production" && (Zt.node, Zt.object.isRequired);
function gz(u) {
  return CL(u);
}
function Sz(u) {
  return hC("MuiSvgIcon", u);
}
eA("MuiSvgIcon", ["root", "colorPrimary", "colorSecondary", "colorAction", "colorError", "colorDisabled", "fontSizeInherit", "fontSizeSmall", "fontSizeMedium", "fontSizeLarge"]);
var Ez = {};
const Cz = (u) => {
  const {
    color: f,
    fontSize: v,
    classes: y
  } = u, S = {
    root: ["root", f !== "inherit" && `color${Fc(f)}`, `fontSize${Fc(v)}`]
  };
  return KN(S, Sz, y);
}, bz = hz("svg", {
  name: "MuiSvgIcon",
  slot: "Root",
  overridesResolver: (u, f) => {
    const {
      ownerState: v
    } = u;
    return [f.root, v.color !== "inherit" && f[`color${Fc(v.color)}`], f[`fontSize${Fc(v.fontSize)}`]];
  }
})(mz(({
  theme: u
}) => {
  var f, v, y, S, T, _, g, L, z, A, F, U, te, B;
  return {
    userSelect: "none",
    width: "1em",
    height: "1em",
    display: "inline-block",
    flexShrink: 0,
    transition: (S = (f = u.transitions) == null ? void 0 : f.create) == null ? void 0 : S.call(f, "fill", {
      duration: (y = (v = (u.vars ?? u).transitions) == null ? void 0 : v.duration) == null ? void 0 : y.shorter
    }),
    variants: [
      {
        props: (M) => !M.hasSvgAsChild,
        style: {
          // the <svg> will define the property that has `currentColor`
          // for example heroicons uses fill="none" and stroke="currentColor"
          fill: "currentColor"
        }
      },
      {
        props: {
          fontSize: "inherit"
        },
        style: {
          fontSize: "inherit"
        }
      },
      {
        props: {
          fontSize: "small"
        },
        style: {
          fontSize: ((_ = (T = u.typography) == null ? void 0 : T.pxToRem) == null ? void 0 : _.call(T, 20)) || "1.25rem"
        }
      },
      {
        props: {
          fontSize: "medium"
        },
        style: {
          fontSize: ((L = (g = u.typography) == null ? void 0 : g.pxToRem) == null ? void 0 : L.call(g, 24)) || "1.5rem"
        }
      },
      {
        props: {
          fontSize: "large"
        },
        style: {
          fontSize: ((A = (z = u.typography) == null ? void 0 : z.pxToRem) == null ? void 0 : A.call(z, 35)) || "2.1875rem"
        }
      },
      // TODO v5 deprecate color prop, v6 remove for sx
      ...Object.entries((u.vars ?? u).palette).filter(([, M]) => M && M.main).map(([M]) => {
        var j, ce;
        return {
          props: {
            color: M
          },
          style: {
            color: (ce = (j = (u.vars ?? u).palette) == null ? void 0 : j[M]) == null ? void 0 : ce.main
          }
        };
      }),
      {
        props: {
          color: "action"
        },
        style: {
          color: (U = (F = (u.vars ?? u).palette) == null ? void 0 : F.action) == null ? void 0 : U.active
        }
      },
      {
        props: {
          color: "disabled"
        },
        style: {
          color: (B = (te = (u.vars ?? u).palette) == null ? void 0 : te.action) == null ? void 0 : B.disabled
        }
      },
      {
        props: {
          color: "inherit"
        },
        style: {
          color: void 0
        }
      }
    ]
  };
})), cg = /* @__PURE__ */ Vt.forwardRef(function(f, v) {
  const y = gz({
    props: f,
    name: "MuiSvgIcon"
  }), {
    children: S,
    className: T,
    color: _ = "inherit",
    component: g = "svg",
    fontSize: L = "medium",
    htmlColor: z,
    inheritViewBox: A = !1,
    titleAccess: F,
    viewBox: U = "0 0 24 24",
    ...te
  } = y, B = /* @__PURE__ */ Vt.isValidElement(S) && S.type === "svg", M = {
    ...y,
    color: _,
    component: g,
    fontSize: L,
    instanceFontSize: f.fontSize,
    inheritViewBox: A,
    viewBox: U,
    hasSvgAsChild: B
  }, j = {};
  A || (j.viewBox = U);
  const ce = Cz(M);
  return /* @__PURE__ */ jd.jsxs(bz, {
    as: g,
    className: nA(ce.root, T),
    focusable: "false",
    color: z,
    "aria-hidden": F ? void 0 : !0,
    role: F ? "img" : void 0,
    ref: v,
    ...j,
    ...te,
    ...B && S.props,
    ownerState: M,
    children: [B ? S.props.children : S, F ? /* @__PURE__ */ jd.jsx("title", {
      children: F
    }) : null]
  });
});
Ez.NODE_ENV !== "production" && (cg.propTypes = {
  // ┌────────────────────────────── Warning ──────────────────────────────┐
  // │ These PropTypes are generated from the TypeScript type definitions. │
  // │    To update them, edit the d.ts file and run `pnpm proptypes`.     │
  // └─────────────────────────────────────────────────────────────────────┘
  /**
   * Node passed into the SVG element.
   */
  children: Zt.node,
  /**
   * Override or extend the styles applied to the component.
   */
  classes: Zt.object,
  /**
   * @ignore
   */
  className: Zt.string,
  /**
   * The color of the component.
   * It supports both default and custom theme colors, which can be added as shown in the
   * [palette customization guide](https://mui.com/material-ui/customization/palette/#custom-colors).
   * You can use the `htmlColor` prop to apply a color attribute to the SVG element.
   * @default 'inherit'
   */
  color: Zt.oneOfType([Zt.oneOf(["inherit", "action", "disabled", "primary", "secondary", "error", "info", "success", "warning"]), Zt.string]),
  /**
   * The component used for the root node.
   * Either a string to use a HTML element or a component.
   */
  component: Zt.elementType,
  /**
   * The fontSize applied to the icon. Defaults to 24px, but can be configure to inherit font size.
   * @default 'medium'
   */
  fontSize: Zt.oneOfType([Zt.oneOf(["inherit", "large", "medium", "small"]), Zt.string]),
  /**
   * Applies a color attribute to the SVG element.
   */
  htmlColor: Zt.string,
  /**
   * If `true`, the root node will inherit the custom `component`'s viewBox and the `viewBox`
   * prop will be ignored.
   * Useful when you want to reference a custom `component` and have `SvgIcon` pass that
   * `component`'s viewBox to the root node.
   * @default false
   */
  inheritViewBox: Zt.bool,
  /**
   * The shape-rendering attribute. The behavior of the different options is described on the
   * [MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/shape-rendering).
   * If you are having issues with blurry icons you should investigate this prop.
   */
  shapeRendering: Zt.string,
  /**
   * The system prop that allows defining system overrides as well as additional CSS styles.
   */
  sx: Zt.oneOfType([Zt.arrayOf(Zt.oneOfType([Zt.func, Zt.object, Zt.bool])), Zt.func, Zt.object]),
  /**
   * Provides a human-readable title for the element that contains it.
   * https://www.w3.org/TR/SVG-access/#Equivalent
   */
  titleAccess: Zt.string,
  /**
   * Allows you to redefine what the coordinates without units mean inside an SVG element.
   * For example, if the SVG element is 500 (width) by 200 (height),
   * and you pass viewBox="0 0 50 20",
   * this means that the coordinates inside the SVG will go from the top left corner (0,0)
   * to bottom right (50,20) and each unit will be worth 10px.
   * @default '0 0 24 24'
   */
  viewBox: Zt.string
});
cg.muiName = "SvgIcon";
var Tz = {};
function xC(u, f) {
  function v(y, S) {
    return /* @__PURE__ */ jd.jsx(cg, {
      "data-testid": `${f}Icon`,
      ref: S,
      ...y,
      children: u
    });
  }
  return Tz.NODE_ENV !== "production" && (v.displayName = `${f}Icon`), v.muiName = cg.muiName, /* @__PURE__ */ Vt.memo(/* @__PURE__ */ Vt.forwardRef(v));
}
const Rz = xC(/* @__PURE__ */ jd.jsx("path", {
  d: "M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2M6 9h12v2H6zm8 5H6v-2h8zm4-6H6V6h12z"
}), "Chat"), wz = xC(/* @__PURE__ */ jd.jsx("path", {
  d: "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6zM19 4h-3.5l-1-1h-5l-1 1H5v2h14z"
}), "Delete"), xz = ({
  threads: u,
  selectedThreadId: f,
  onSelectThread: v,
  onNewThread: y,
  onDeleteThread: S
}) => /* @__PURE__ */ _e.createElement("div", { className: "w-60 flex flex-col border-r border-gray-200 bg-gray-50 overflow-hidden" }, /* @__PURE__ */ _e.createElement("div", { className: "p-3 border-b border-gray-200 bg-white" }, /* @__PURE__ */ _e.createElement("h2", { className: "font-semibold text-gray-700 mb-2 flex items-center" }, /* @__PURE__ */ _e.createElement(Rz, { className: "mr-2" }), " Threads"), /* @__PURE__ */ _e.createElement(
  "button",
  {
    onClick: y,
    className: "w-full py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors duration-150 ease-in-out text-sm font-medium"
  },
  "New Thread"
)), /* @__PURE__ */ _e.createElement("div", { className: "flex-1 overflow-y-auto" }, u.map((T) => /* @__PURE__ */ _e.createElement(
  "div",
  {
    key: T.thread_id,
    className: `
              px-3 py-2.5 cursor-pointer hover:bg-blue-50 
              ${f === T.thread_id ? "bg-blue-100" : ""}
              flex justify-between items-center
            `,
    onClick: () => v(T.thread_id)
  },
  /* @__PURE__ */ _e.createElement(
    "div",
    {
      className: "text-sm font-medium text-gray-800 truncate flex-grow"
    },
    T.name || "Unnamed Thread"
  ),
  /* @__PURE__ */ _e.createElement(
    "button",
    {
      onClick: (_) => {
        _.stopPropagation(), S(T.thread_id);
      },
      className: "text-red-500 hover:text-red-700 ml-2 p-1 text-xs",
      title: "Delete thread"
    },
    /* @__PURE__ */ _e.createElement(wz, { fontSize: "small" })
  )
)))), _z = xC(/* @__PURE__ */ jd.jsx("path", {
  d: "m22.7 19-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4"
}), "Build"), Uw = ({ artifacts: u }) => /* @__PURE__ */ _e.createElement("div", { className: "mt-2" }, /* @__PURE__ */ _e.createElement("div", { className: "flex gap-2 flex-wrap" }, u.map((f, v) => /* @__PURE__ */ _e.createElement(
  "a",
  {
    key: v,
    href: `cursor://file/${f.path}`,
    target: "_blank",
    rel: "noopener noreferrer",
    className: `flex-shrink-0 text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full 
                   hover:bg-blue-50 hover:border-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300`
  },
  f.name || `Artifact ${v + 1}`
)))), kz = ({ content: u, messageId: f, artifacts: v }) => {
  var S;
  const y = v.filter((T) => T.message_id === f);
  return /* @__PURE__ */ _e.createElement("div", { className: "flex flex-col items-end" }, /* @__PURE__ */ _e.createElement(
    "div",
    {
      className: "px-4 py-2 rounded-lg max-w-[70%] bg-blue-600 text-white",
      style: { whiteSpace: "pre-wrap" }
    },
    (S = u == null ? void 0 : u[0]) == null ? void 0 : S.text
  ), y.length > 0 && /* @__PURE__ */ _e.createElement(Uw, { artifacts: y }));
}, Oz = ({ content: u, messageId: f, artifacts: v }) => {
  const [y, S] = Vt.useState({}), T = v.filter((L) => L.message_id === f), _ = (L, z) => {
    S((A) => ({
      ...A,
      [`${L}-${z}`]: !A[`${L}-${z}`]
    }));
  }, g = (L, z) => !!y[`${L}-${z}`];
  return /* @__PURE__ */ _e.createElement("div", { className: "flex flex-col" }, /* @__PURE__ */ _e.createElement("div", { className: "flex justify-start" }, /* @__PURE__ */ _e.createElement(
    "div",
    {
      className: "px-4 py-2 rounded-lg max-w-[70%] bg-gray-100 text-gray-800 border border-gray-200",
      style: { whiteSpace: "pre-wrap" }
    },
    /* @__PURE__ */ _e.createElement("div", { className: "agent-structured-content flex flex-col gap-2" }, u == null ? void 0 : u.map((L, z) => {
      if (L.kind === "thought")
        return /* @__PURE__ */ _e.createElement("div", { key: z, className: "thought-content italic text-gray-600 border-l-2 border-gray-400 pl-2" }, L.thought);
      if (L.kind === "text")
        return /* @__PURE__ */ _e.createElement("div", { key: z, className: "text-content" }, L.text);
      if (L.kind === "tool_call") {
        const F = {
          pending: "bg-gray-100 text-gray-600",
          running: "bg-blue-100 text-blue-700",
          streaming: "bg-purple-100 text-purple-700",
          finished: "bg-green-100 text-green-700",
          failed: "bg-red-100 text-red-700"
        }[L.status] || "bg-gray-100", U = L.status === "running" || L.status === "streaming";
        let te = L.arguments_raw;
        try {
          const j = JSON.parse(L.arguments_raw);
          te = JSON.stringify(j, null, 2);
        } catch {
        }
        const B = `tool-${z}`;
        let M = L.result;
        try {
          const j = JSON.parse(L.result);
          M = JSON.stringify(j, null, 2);
        } catch {
        }
        return /* @__PURE__ */ _e.createElement("div", { key: z, className: "tool-call-content border rounded-md overflow-hidden" }, /* @__PURE__ */ _e.createElement("div", { className: "tool-header bg-gray-200 px-3 py-1.5 font-medium flex justify-between items-center" }, /* @__PURE__ */ _e.createElement("span", null, /* @__PURE__ */ _e.createElement(_z, { fontSize: "inherit", className: "mr-2" }), " ", L.name), /* @__PURE__ */ _e.createElement("div", { className: "flex items-center" }, U && /* @__PURE__ */ _e.createElement("div", { className: "animate-spin mr-2 h-4 w-4 text-blue-600" }, /* @__PURE__ */ _e.createElement("svg", { xmlns: "http://www.w3.org/2000/svg", fill: "none", viewBox: "0 0 24 24" }, /* @__PURE__ */ _e.createElement("circle", { className: "opacity-25", cx: "12", cy: "12", r: "10", stroke: "currentColor", strokeWidth: "4" }), /* @__PURE__ */ _e.createElement("path", { className: "opacity-75", fill: "currentColor", d: "M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" }))), /* @__PURE__ */ _e.createElement("span", { className: `text-xs px-2 py-0.5 rounded-full ${F}` }, L.status))), /* @__PURE__ */ _e.createElement("div", { className: "px-3 py-2" }, /* @__PURE__ */ _e.createElement("div", { className: "tool-args mb-2" }, /* @__PURE__ */ _e.createElement(
          "button",
          {
            onClick: () => _(B, "args"),
            className: "text-xs text-gray-500 mb-1 flex items-center w-full justify-between hover:bg-gray-50 p-1 rounded"
          },
          /* @__PURE__ */ _e.createElement("span", null, "Arguments:"),
          /* @__PURE__ */ _e.createElement("span", { className: "text-gray-400" }, g(B, "args") ? "▼" : "►")
        ), g(B, "args") && /* @__PURE__ */ _e.createElement("pre", { className: "text-xs bg-gray-50 p-2 rounded overflow-x-auto" }, te)), L.result && /* @__PURE__ */ _e.createElement("div", { className: "tool-result" }, /* @__PURE__ */ _e.createElement(
          "button",
          {
            onClick: () => _(B, "result"),
            className: "text-xs text-gray-500 mb-1 flex items-center w-full justify-between hover:bg-gray-50 p-1 rounded"
          },
          /* @__PURE__ */ _e.createElement("span", null, "Result:"),
          /* @__PURE__ */ _e.createElement("span", { className: "text-gray-400" }, g(B, "result") ? "▼" : "►")
        ), g(B, "result") && /* @__PURE__ */ _e.createElement("pre", { className: "text-xs bg-gray-50 p-2 rounded overflow-x-auto" }, M)), L.error && /* @__PURE__ */ _e.createElement("div", { className: "tool-error" }, /* @__PURE__ */ _e.createElement(
          "button",
          {
            onClick: () => _(B, "error"),
            className: "text-xs text-gray-500 mb-1 flex items-center w-full justify-between hover:bg-gray-50 p-1 rounded"
          },
          /* @__PURE__ */ _e.createElement("span", null, "Error:"),
          /* @__PURE__ */ _e.createElement("span", { className: "text-gray-400" }, g(B, "error") ? "▼" : "►")
        ), g(B, "error") && /* @__PURE__ */ _e.createElement("pre", { className: "text-xs bg-red-50 text-red-700 p-2 rounded overflow-x-auto" }, L.error))));
      }
      return null;
    }))
  )), T.length > 0 && /* @__PURE__ */ _e.createElement("div", { className: "flex justify-start mt-1 ml-2" }, /* @__PURE__ */ _e.createElement(Uw, { artifacts: T })));
}, Dz = ({
  threadName: u,
  messages: f,
  onSendMessage: v,
  isLoading: y,
  activeThreadArtifacts: S
}) => {
  const [T, _] = Vt.useState(""), g = Vt.useRef(null), L = () => {
    const A = T.trim();
    A && (v(A), _(""));
  };
  Vt.useEffect(() => {
    var A;
    (A = g.current) == null || A.scrollIntoView({ behavior: "smooth" });
  }, [f]);
  const z = S.filter((A) => !A.message_id);
  return /* @__PURE__ */ _e.createElement("div", { className: "flex-1 flex flex-col overflow-hidden" }, /* @__PURE__ */ _e.createElement("div", { className: "flex-shrink-0 bg-white border-b border-gray-200 px-4 py-2" }, /* @__PURE__ */ _e.createElement("h2", { className: "font-semibold text-gray-800" }, u || "No thread selected")), /* @__PURE__ */ _e.createElement("div", { className: "flex-1 overflow-y-auto bg-gray-50 p-4" }, /* @__PURE__ */ _e.createElement("div", { className: "flex flex-col space-y-3" }, f.map((A, F) => /* @__PURE__ */ _e.createElement("div", { key: F }, A.role === "user" ? /* @__PURE__ */ _e.createElement(
    kz,
    {
      content: A.content,
      messageId: A.message_id,
      artifacts: S
    }
  ) : /* @__PURE__ */ _e.createElement(
    Oz,
    {
      content: A.content,
      messageId: A.message_id,
      artifacts: S
    }
  ))), /* @__PURE__ */ _e.createElement("div", { ref: g }))), z.length > 0 && /* @__PURE__ */ _e.createElement("div", { className: "flex-shrink-0 border-t border-gray-200 bg-gray-50 p-2" }, /* @__PURE__ */ _e.createElement("div", { className: "flex justify-between items-center mb-1" }, /* @__PURE__ */ _e.createElement("span", { className: "text-xs font-medium text-gray-500" }, "Thread Artifacts"), /* @__PURE__ */ _e.createElement("span", { className: "text-xs text-gray-400" }, z.length, " item(s)")), /* @__PURE__ */ _e.createElement("div", { className: "overflow-x-auto pb-1" }, /* @__PURE__ */ _e.createElement("div", { className: "flex gap-2" }, z.map((A, F) => /* @__PURE__ */ _e.createElement(
    "a",
    {
      key: F,
      href: `cursor://file/${A.path}`,
      target: "_blank",
      rel: "noopener noreferrer",
      className: `flex-shrink-0 text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full 
                           hover:bg-blue-50 hover:border-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300`
    },
    A.name || `Artifact ${F + 1}`
  ))))), /* @__PURE__ */ _e.createElement("div", { className: "flex-shrink-0 border-t border-gray-200 p-3 bg-white" }, /* @__PURE__ */ _e.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ _e.createElement(
    "input",
    {
      type: "text",
      className: `flex-1 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${y ? "bg-gray-100 cursor-not-allowed" : ""}`,
      placeholder: y ? "Waiting for response..." : "Type your message...",
      value: T,
      onChange: (A) => _(A.target.value),
      onKeyDown: (A) => {
        A.key === "Enter" && !y && (A.preventDefault(), L());
      },
      disabled: y
    }
  ), /* @__PURE__ */ _e.createElement(
    "button",
    {
      onClick: L,
      disabled: y,
      className: `px-4 py-2 rounded font-medium ${y ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700 text-white"}`
    },
    "Send"
  ))));
}, Nz = ({ isLoading: u, statusMessage: f }) => /* @__PURE__ */ _e.createElement("div", { className: "h-full w-full flex items-center px-3 bg-gray-50" }, /* @__PURE__ */ _e.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ _e.createElement(
  "div",
  {
    className: `w-2 h-2 rounded-full ${u ? "bg-blue-500 animate-pulse" : "bg-green-500"}`
  }
), /* @__PURE__ */ _e.createElement("span", { className: "text-xs text-gray-600" }, f))), Az = ({
  threads: u,
  selected_thread_id: f,
  selected_thread_name: v,
  messages: y,
  is_loading: S,
  status_message: T,
  active_thread_artifacts: _,
  sendMsgToPython: g
}) => {
  const L = (U) => {
    g({ type: "select_thread", thread_id: U });
  }, z = () => {
    g({ type: "new_thread" });
  }, A = (U) => {
    g({ type: "user_input", text: U });
  }, F = (U) => {
    g({ type: "delete_thread", thread_id: U });
  };
  return /* @__PURE__ */ _e.createElement(
    "div",
    {
      className: "w-[800px] h-[800px] border border-gray-300",
      style: {
        display: "grid",
        gridTemplateRows: "minmax(0, 1fr) auto",
        overflow: "hidden"
      }
    },
    /* @__PURE__ */ _e.createElement("div", { className: "flex w-full overflow-hidden" }, /* @__PURE__ */ _e.createElement(
      xz,
      {
        threads: u,
        selectedThreadId: f,
        onSelectThread: L,
        onNewThread: z,
        onDeleteThread: F
      }
    ), /* @__PURE__ */ _e.createElement(
      Dz,
      {
        threadName: v || "",
        messages: y,
        onSendMessage: A,
        isLoading: S,
        activeThreadArtifacts: _
      }
    )),
    /* @__PURE__ */ _e.createElement("div", { className: "w-full h-8 border-t border-gray-200 bg-gray-50" }, /* @__PURE__ */ _e.createElement(Nz, { isLoading: S, statusMessage: T }))
  );
}, Mz = () => {
  const [u] = $c("threads_out"), [f] = $c("messages_out"), [v] = $c("active_thread_artifacts"), [y] = $c("selected_thread_id_out"), [S] = $c("selected_thread_name_out"), [T] = $c("is_loading"), [_] = $c("status_message"), g = iw(), L = (z) => {
    g == null || g.send(z);
  };
  return /* @__PURE__ */ _e.createElement(
    Az,
    {
      threads: u || [],
      selected_thread_id: y,
      selected_thread_name: S,
      messages: f || [],
      is_loading: T,
      status_message: _,
      active_thread_artifacts: v || [],
      sendMsgToPython: L
    }
  );
}, Pz = LN(() => /* @__PURE__ */ _e.createElement(Mz, null));
export {
  Pz as render
};
